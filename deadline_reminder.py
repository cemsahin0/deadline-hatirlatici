#!/usr/bin/env python3
"""
Deadline Hatırlatıcı - Apple Mail'deki mailleri okur, Claude ile son tarihleri
(deadline) çıkarır ve 30 gün içinde olanları data/deadlines.json'a yazar.
Post-it penceresi (postit.py) bu dosyayı gösterir.

Kullanım:
  .venv/bin/python deadline_reminder.py            # yeni mailleri işle
  .venv/bin/python deadline_reminder.py --rebuild  # sadece deadlines.json'u yeniden üret
"""
import argparse
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

import shutil

import calendar_sync
import docs
import sites

# ---- Ayarlar ---------------------------------------------------------------
LOOKBACK_DAYS = 120        # kaç günlük mailler taransın (~4 ay)
WINDOW_DAYS = 30           # deadline'ı kaç gün içinde olanlar gösterilsin
BATCH_SIZE = 25            # Claude'a tek seferde gönderilecek mail sayısı
MODEL = "opus"            # Claude hesabındaki en güncel Opus modeli
# ---------------------------------------------------------------------------

BASE = Path(__file__).resolve().parent
# Kayıtlar iCloud'un dokunmadığı yerde: Belgeler/Masaüstü iCloud'daysa macOS dosyaları buluta alıp
# Mac'ten silebiliyor ve arka plandaki tarama onları okuyamıyor.
DATA = Path(os.environ.get("DEADLINE_DATA") or
            Path.home() / "Library/Application Support/Deadline Hatirlatici/data")
STATE_FILE = DATA / "state.json"
OUT_FILE = DATA / "deadlines.json"
LOCK_FILE = DATA / ".lock"
FETCH_JS = BASE / "fetch_mail.js"
SITES_FILE = DATA / "sites.txt"   # takip edilen ders siteleri (her satıra bir link)
SETTINGS_FILE = DATA / "settings.json"   # {"allowed_senders": ["@okul.edu", ...]}; boş = hepsi

SCHEMA = {
    "type": "object",
    "properties": {
        "deadlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mail_id": {"type": "string"},
                    "title": {"type": "string"},
                    "deadline_date": {"type": "string"},
                    "deadline_time": {"type": "string"},
                    "source": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "cancelled"]},
                },
                "required": ["mail_id", "title", "deadline_date", "deadline_time", "source", "status"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["deadlines"],
    "additionalProperties": False,
}

SYSTEM = """Sen bir üniversite öğrencisinin maillerini tarayan bir asistansın. Görevin, öğrencinin \
kendisinin bir şey yapması gereken GERÇEK son tarihleri (deadline) bulmak: ödev/proje teslimi, \
başvuru, kayıt, form doldurma, ödeme, sınav, onay/etik başvurusu, belge teslimi, zorunlu bir \
hesap/güvenlik ayarının son günü gibi.

Kurallar:
- Reklam ve kampanya bitişlerini ("indirim pazar günü bitiyor" vb.), haber bültenlerini ve \
öğrencinin bir şey yapmasını gerektirmeyen etkinlik tarihlerini ALMA.
- Göreceli tarihleri ("cuma", "7 gün içinde", "yarın") mailin gönderilme tarihine göre gerçek \
tarihe çevir.
- deadline_date her zaman YYYY-MM-DD olsun. Saat belliyse deadline_time "HH:MM" (24 saat), \
değilse "".
- title: kısa ve net, Türkçe, en fazla ~60 karakter. Ders kodu varsa başa koy \
(örn. "CS405 Project 1 teslimi").
- source: kimden geldiği, kısa (örn. "SUCourse - CS405", "Internship Office").
- Mailler eskiden yeniye sıralı gelir. Aynı iş zaten "bilinen deadline'lar" listesinde varsa \
AYNI title'ı birebir kullan. Bu, iş başka bir kaynaktan (mail, ders web sitesi, PDF/Word belgesi) \
gelmiş olsa ve farklı yazılmış olsa da geçerli: aynı ders kodu + aynı iş (aynı sınav, aynı ödev, \
aynı proje aşaması) = aynı title. Örn. listede "ENS210 Midterm" varken sitede "Midterm 1" ya da \
mailde "ENS 210 ara sınav" görürsen title'ı "ENS210 Midterm" yaz.
- ÇOK ÖNEMLİ - uzatma/değişiklik: Bir mail önceden verilmiş bir tarihi değiştiriyorsa ("deadline \
extended", "new deadline", "ertelendi", "uzatıldı", "postponed", "moved to") listedeki title'ı \
birebir kullanıp YENİ tarihi yaz, status "active". İş iptal edildiyse aynı title ile \
status "cancelled" yaz (tarih olarak eski tarihi kullan).
- Hatırlatma mailleri ("due in 7 days", "Due on Sunday ...") da geçerlidir; tarihi mailin \
içindeki açık tarihten al.
- Bir mailde deadline yoksa o mail için hiçbir şey ekleme. Emin değilsen ekleme.
- mail_id olarak maile verilen id'yi aynen yaz."""


def log(*a):
    line = " ".join([f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}]", *map(str, a)])
    print(line, flush=True)
    if not sys.stdout.isatty():  # launchd altında: post-it'in okuduğu log'a da yaz
        try:
            with open(DATA / "reminder.log", "a") as f:
                f.write(line + "\n")
        except OSError:
            pass


def _claude_dirs():
    """claude aracının olabileceği klasörler; en yeni nvm Node sürümü önce."""
    nvm = sorted(Path.home().glob(".nvm/versions/node/*/bin"),
                 key=lambda p: [int(x) for x in p.parent.name.lstrip("v").split(".") if x.isdigit()],
                 reverse=True)
    return [str(p) for p in nvm] + [str(Path.home() / ".local/bin"), "/opt/homebrew/bin", "/usr/local/bin"]


ENV = {**os.environ, "PATH": ":".join(_claude_dirs() + [os.environ.get("PATH", "/usr/bin:/bin")])}
ENV.pop("ANTHROPIC_API_KEY", None)  # Claude hesabıyla girişi kullan
CLAUDE = shutil.which("claude", path=ENV["PATH"]) or "claude"
CODEX = shutil.which("codex", path=ENV["PATH"]) or "codex"


def engine():
    """Hangi yapay zekâ aracı kullanılacak: install.sh ayara yazar; yoksa kurulu olana bakılır."""
    try:
        e = json.loads(SETTINGS_FILE.read_text()).get("engine")
    except Exception:
        e = None
    if e in ("claude", "codex"):
        return e
    if not shutil.which("claude", path=ENV["PATH"]) and shutil.which("codex", path=ENV["PATH"]):
        return "codex"
    return "claude"


class ClaudeNotLoggedIn(Exception):
    """Yapay zekâ aracına (Claude Code ya da Codex) giriş yapılmamış."""


def ask_claude(system, text, schema, effort="low"):
    """claude komut aracıyla (Claude hesabı üzerinden) yapılandırılmış JSON yanıt al."""
    cmd = [CLAUDE, "-p", "--model", MODEL, "--effort", effort,
           "--output-format", "json", "--json-schema", json.dumps(schema),
           "--system-prompt", system, "--tools", "", "--no-session-persistence",
           "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"]
    out = subprocess.run(cmd, input=text, capture_output=True, text=True, env=ENV,
                         cwd=DATA, timeout=900)
    try:
        res = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude aracı beklenmeyen çıktı verdi: {out.stdout[:300]} {out.stderr[:300]}")
    if res.get("is_error"):
        msg = str(res.get("result", ""))
        if "login" in msg.lower() or "api key" in msg.lower() or "auth" in msg.lower():
            raise ClaudeNotLoggedIn(msg)
        raise RuntimeError(f"Claude hatası: {msg[:300]}")
    data = res.get("structured_output")
    if data is None:
        data = json.loads(res["result"])
    return data


CODEX_RULES = ("\n\nÖNEMLİ: Hiçbir komut çalıştırma, dosya okuma ya da yazma. Sadece aşağıdaki metne bakarak "
               "cevap ver. Cevabın SADECE şu JSON şemasına uyan tek bir JSON nesnesi olsun, başka hiçbir "
               "şey yazma:\n")


def ask_codex(system, text, schema, effort="low"):
    """codex komut aracıyla (ChatGPT hesabı üzerinden) JSON yanıt al."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        schema_file, out_file = Path(tmp) / "schema.json", Path(tmp) / "cevap.txt"
        schema_file.write_text(json.dumps(schema))
        work = Path(tmp) / "bos"
        work.mkdir()
        prompt = system + CODEX_RULES + json.dumps(schema, ensure_ascii=False) + "\n\n---\n\n" + text
        optional = ["--output-schema", str(schema_file), "--ephemeral", "--color", "never",
                    "-c", f'model_reasoning_effort="{effort}"']
        base = [CODEX, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-o", str(out_file)]
        for extra in (optional, []):   # eski Codex sürümleri bu seçenekleri tanımıyorsa onlarsız dene
            out = subprocess.run(base + extra + ["-"], input=prompt, capture_output=True, text=True,
                                 env=ENV, cwd=work, timeout=900)
            if out.returncode == 0 or "unexpected argument" not in out.stderr:
                break
        err = (out.stderr + out.stdout).lower()
        if out.returncode != 0:
            if any(w in err for w in ("not logged in", "login", "unauthorized", "401", "auth")):
                raise ClaudeNotLoggedIn(out.stderr[-300:])
            raise RuntimeError(f"Codex hatası: {out.stderr.strip()[-300:]}")
        answer = out_file.read_text() if out_file.exists() else out.stdout
    start, end = answer.find("{"), answer.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"Codex beklenmeyen cevap verdi: {answer[:300]}")
    return json.loads(answer[start:end + 1])


def ask_ai(system, text, schema, effort="low"):
    if engine() == "codex":
        return ask_codex(system, text, schema, effort)
    return ask_claude(system, text, schema, effort)


def mail_choice_made():
    """Kullanıcı hangi maillerin okunacağını seçti mi? (Seçmeden hiçbir mail gönderilmez.)"""
    try:
        return "allowed_senders" in json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return False


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    tmp.replace(STATE_FILE)


def allowed_senders():
    try:
        return [p for p in json.loads(SETTINGS_FILE.read_text()).get("allowed_senders", []) if p.strip()]
    except Exception:
        return []


def sender_allowed(sender, patterns):
    """fetch_mail.js'teki senderAllowed ile aynı kural."""
    if not patterns:
        return True
    s = (sender or "").lower()
    addr = s[s.find("<") + 1:s.find(">")] if "<" in s and ">" in s else s
    addr = addr.strip()
    for p in patterns:
        p = p.strip().lower()
        if not p.startswith("@") and "@" not in p:
            p = "@" + p
        if (p.startswith("@") and (addr.endswith(p) or addr.endswith("." + p[1:]))) or addr == p:
            return True
    return False


def fetch_new_mails(known_ids, limit):
    known_file = DATA / ".known_ids.json"
    known_file.write_text(json.dumps(list(known_ids)))
    allow_file = DATA / ".allowed.json"
    allow_file.write_text(json.dumps(allowed_senders()))
    out = subprocess.run(
        ["osascript", "-l", "JavaScript", str(FETCH_JS), str(LOOKBACK_DAYS), str(known_file), str(limit),
         str(allow_file)],
        capture_output=True, text=True, timeout=1800,
    )
    if out.returncode != 0:
        raise RuntimeError(f"Mail okunamadı: {out.stderr.strip()}")
    return json.loads(out.stdout)


def all_deadlines(state):
    """Tüm işlenmiş maillerden deadline'ları topla; aynı title için en yeni maildekini tut."""
    best = {}
    recs = sorted(state["processed"].items(), key=lambda kv: kv[1].get("date", ""))
    for mid, rec in recs:  # eskiden yeniye: sonraki mail (uzatma/iptal) öncekini ezer
        for d in rec.get("deadlines", []):
            key = d["title"].strip().lower()
            if d.get("status") == "cancelled":
                best.pop(key, None)
                continue
            best[key] = {**d, "mail_id": mid, "mail_subject": rec.get("subject", ""),
                         "mail_date": rec.get("date", "")}
    return list(best.values())


def known_titles_text(state):
    since = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    items = [d for d in all_deadlines(state) if d["deadline_date"] >= since]
    if not items:
        return "(henüz yok)"
    items.sort(key=lambda d: d["deadline_date"])
    return "\n".join(f"- {d['title']} ({d['deadline_date']}, {d['source']})" for d in items[-150:])


def extract_deadlines(mails, state):
    today = dt.date.today()
    parts = [f"Bugünün tarihi: {today.isoformat()} ({today.strftime('%A')}).",
             "", "Bilinen deadline'lar:", known_titles_text(state), "", "Mailler:"]
    for m in mails:
        parts.append(
            f"\n<mail id=\"{m['id']}\">\nKimden: {m['sender']}\nTarih: {m['date']}\n"
            f"Konu: {m['subject']}\n\n{m['content']}\n</mail>"
        )
    found = ask_ai(SYSTEM, "\n".join(parts), SCHEMA, "low")["deadlines"]
    valid = []
    for d in found:
        try:
            dt.date.fromisoformat(d["deadline_date"])
            valid.append(d)
        except ValueError:
            continue
    return valid


MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "drop": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"index": {"type": "integer"}, "reason": {"type": "string"}},
                "required": ["index", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["drop"],
    "additionalProperties": False,
}

MERGE_SYSTEM = """Sana bir öğrencinin gelecekteki deadline listesi verilecek. Kayıtlar farklı \
kaynaklardan gelir: mail, dersin web sitesi, öğrencinin eklediği PDF/Word belgesi. Bazıları AYNI işin \
tekrarıdır: farklı yazılmış başlıklar (Türkçe/İngilizce, "Midterm" / "Ara sınav" / "Midterm 1", \
"HW2" / "Homework 2" / "Assignment 2"), hatırlatma mailleri, ya da hocanın sonradan uzattığı/değiştirdiği \
tarihler. Aynı ders kodu + aynı iş ise aynı kayıttır, tarihleri farklı olsa bile.

Her grupta TEK kayıt kalsın:
1. Bir kayıt açıkça değişiklik/uzatma duyurusundan geliyorsa (konu ya da başlıkta "extended", "new \
deadline", "ertelendi", "uzatıldı", "değişti" vb.) onu tut.
2. Yoksa bilginin en yeni olduğu kaydı tut (görülme tarihi en yeni olan).
3. Tarih aynıysa saati belli olan / başlığı daha açıklayıcı olanı tut.
Grubun geri kalanını "drop" listesine koy ve reason'da hangi kayıtla birleştirdiğini yaz.

Farklı işleri asla birleştirme: Midterm 1 ile Midterm 2, Project Milestone 1 ile Milestone 2, \
farklı dersler, aynı dersin farklı ödevleri. Emin değilsen bırakma."""


def merge_duplicates(state):
    """Uzatma/tekrar kayıtlarını Claude ile ayıkla; sonucu state['dropped'] içine yazar."""
    today = dt.date.today().isoformat()
    items = sorted((d for d in all_deadlines(state) if d["deadline_date"] >= today),
                   key=lambda d: d["deadline_date"])
    if len(items) < 2:
        state["dropped"] = []
        return
    def kind(d):
        mid = str(d.get("mail_id", ""))
        return "ders sitesi" if mid.startswith("site:") else "belge" if mid.startswith("file:") else "mail"
    lines = [f"[{i}] {d['title']} | tarih: {d['deadline_date']} {d['deadline_time']} | "
             f"kaynak türü: {kind(d)} ({d['source']}) | başlık: \"{d['mail_subject']}\" | "
             f"görülme tarihi: {d['mail_date'][:16]}"
             for i, d in enumerate(items)]
    try:
        result = ask_ai(MERGE_SYSTEM, "\n".join(lines), MERGE_SCHEMA, "medium")
    except RuntimeError as e:
        log(f"Birleştirme adımı atlandı: {e}")
        return
    dropped = []
    for x in result["drop"]:
        if 0 <= x["index"] < len(items):
            d = items[x["index"]]
            dropped.append(f"{d['title'].strip().lower()}|{d['deadline_date']}")
            log(f"  - tekrar/eski tarih çıkarıldı: {d['deadline_date']} {d['title']} ({x['reason']})")
    state["dropped"] = dropped


def write_output(state):
    today = dt.date.today()
    limit = today + dt.timedelta(days=WINDOW_DAYS)
    dropped = set(state.get("dropped", []))
    items = []
    for d in all_deadlines(state):
        if f"{d['title'].strip().lower()}|{d['deadline_date']}" in dropped:
            continue
        day = dt.date.fromisoformat(d["deadline_date"])
        if today <= day <= limit:
            items.append({**d, "days_left": (day - today).days})
    items.sort(key=lambda d: (d["deadline_date"], d["deadline_time"] or "99:99"))
    OUT_FILE.write_text(json.dumps(
        {"updated": dt.datetime.now().isoformat(timespec="minutes"), "items": items},
        ensure_ascii=False, indent=1))
    return items


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def import_files(paths, state):
    """Kullanıcının seçtiği PDF/Word dosyalarını oku, deadline'larını ekle, sonucu bildirimle söyle."""
    found_any = False
    for path in paths:
        p = Path(path).expanduser().resolve()
        name = p.name
        try:
            text = docs.file_text(p)
        except docs.Unreadable as e:
            log(f"Dosya okunamadı ({name}): {e}")
            sites.notify(f"Dosya: {name}", str(e))
            continue
        except Exception as e:
            log(f"Dosya okunamadı ({name}): {e}")
            sites.notify(f"Dosya: {name}", "Dosya okunamadı. macOS izin sorduysa İzin Ver deyip tekrar dene.")
            continue
        log(f"Dosya okunuyor: {name}")
        key = f"file:{p}"
        page = {"id": key, "sender": "Dosya", "date": now_iso(), "subject": name,
                "content": docs.DOC_NOTE + text[:sites.MAX_CHARS]}
        found = extract_deadlines([page], state)
        state["processed"][key] = {
            "subject": name, "sender": "Dosya", "date": page["date"], "path": str(p),
            "deadlines": [{k: d[k] for k in ("title", "deadline_date", "deadline_time", "source", "status")}
                          for d in found],
        }
        save_state(state)
        for d in found:
            log(f"  + {d['deadline_date']} {d['title']}  (dosya)")
        sites.notify(f"Dosya: {name}", sites.result_message(found, WINDOW_DAYS))
        found_any = found_any or bool(found)
    return found_any


def sync_calendar(state):
    """Ayarlarda açıksa: gelecekteki tüm aktif deadline'ları (bitirilenler hariç) Takvim'e yaz."""
    try:
        settings = json.loads(SETTINGS_FILE.read_text())
    except Exception:
        settings = {}
    if not settings.get("calendar"):
        return
    def read(path, default):
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    done = set(read(DATA / "done.json", []))
    dropped = set(state.get("dropped", []))
    today = dt.date.today().isoformat()
    items = []
    for d in all_deadlines(state) + read(DATA / "manual.json", []):
        if d.get("repeat"):   # haftalık kendi notun: takvimde tekrarlanan etkinlik olarak hep dursun
            items.append(d)
            continue
        key = f"{d['title'].strip().lower()}|{d['deadline_date']}"
        if d["deadline_date"] >= today and key not in dropped and key not in done:
            items.append(d)
    try:
        calendar_sync.sync(items, DATA / "calendar.json", log)
    except Exception as e:
        log(f"Takvime yazılamadı: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="Mail okumadan sadece listeyi yenile")
    ap.add_argument("--sites-now", action="store_true", help="Ders sitelerini beklemeden kontrol et")
    ap.add_argument("--add-file", nargs="+", metavar="DOSYA", help="PDF/Word dosyalarını oku ve ekle")
    ap.add_argument("--remove-file", nargs="+", metavar="DOSYA", help="Eklenen dosyaları listeden çıkar")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    lock = open(LOCK_FILE, "w")
    if args.add_file or args.remove_file:
        fcntl.flock(lock, fcntl.LOCK_EX)   # kullanıcı istedi: süren tarama bitene kadar bekle
    else:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("Başka bir tarama zaten çalışıyor, çıkılıyor.")
            return

    state = load_state()
    if args.add_file:
        if import_files(args.add_file, state):
            merge_duplicates(state)
            save_state(state)
        write_output(state)
        sync_calendar(state)
        return
    if args.remove_file:
        for f in args.remove_file:
            state["processed"].pop(f"file:{Path(f).expanduser().resolve()}", None)
        save_state(state)
        write_output(state)
        sync_calendar(state)
        log(f"{len(args.remove_file)} dosya listeden çıkarıldı.")
        return
    if args.rebuild:
        log(f"{len(write_output(state))} deadline yazıldı.")
        sync_calendar(state)
        return

    # İzin listesi genişletildiyse, daha önce gizli diye atlanan mailler tekrar değerlendirilsin
    allow = allowed_senders()
    for k in [k for k, r in state["processed"].items() if r.get("skipped") and sender_allowed(r.get("sender"), allow)]:
        del state["processed"][k]

    found_any = False
    chosen = mail_choice_made()
    if not chosen:
        log("Hangi maillerin okunacağı henüz seçilmedi; mailler taranmıyor (post-it soruyor).")
    while chosen:
        res = fetch_new_mails(state["processed"].keys(), BATCH_SIZE)
        mails = [m for m in res["messages"] if not m.get("skipped")]
        skipped = [m for m in res["messages"] if m.get("skipped")]
        if not res["messages"]:
            break
        for m in skipped:  # gizli tutulan mail: Claude'a gönderilmez, sadece "bakıldı" diye işaretlenir
            state["processed"][m["id"]] = {"sender": m["sender"], "date": m["date"], "skipped": True,
                                           "deadlines": []}
        if skipped:
            log(f"{len(skipped)} mail izinli gönderici listesinde olmadığı için gönderilmedi")
        if not mails:
            save_state(state)
            continue
        done = sum(1 for _ in state["processed"])
        log(f"{len(mails)} yeni mail işleniyor (aralıkta toplam {res['total_in_range']}, işlenmiş {done})")
        found = extract_deadlines(mails, state)
        by_mail = {}
        for d in found:
            by_mail.setdefault(d["mail_id"], []).append(
                {k: d[k] for k in ("title", "deadline_date", "deadline_time", "source", "status")})
        for m in mails:
            state["processed"][m["id"]] = {
                "subject": m["subject"], "sender": m["sender"], "date": m["date"],
                "deadlines": by_mail.get(m["id"], []),
            }
        save_state(state)
        write_output(state)  # post-it ilk taramada da kademeli dolsun
        if found:
            found_any = True
            for d in found:
                log(f"  + {d['deadline_date']} {d['title']}")

    try:
        if sites.check_sites(state, SITES_FILE, extract_deadlines, log, force=args.sites_now):
            found_any = True
        save_state(state)
    except ClaudeNotLoggedIn:
        raise
    except Exception as e:
        log(f"Ders siteleri kontrol edilemedi: {e}")

    if found_any or "dropped" not in state:
        log("Tekrarlar ve uzatmalar kontrol ediliyor...")
        merge_duplicates(state)
        save_state(state)
    items = write_output(state)
    sync_calendar(state)
    log(f"Bitti. Önümüzdeki {WINDOW_DAYS} günde {len(items)} deadline var.")


if __name__ == "__main__":
    try:
        main()
    except ClaudeNotLoggedIn:
        if engine() == "codex":
            log("HATA: Codex girişi yok. Terminalde 'codex login' çalıştır.")
        else:
            log("HATA: Claude girişi yok. Terminalde 'claude auth login' çalıştır.")
        sys.exit(1)
