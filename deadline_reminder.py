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

# ---- Ayarlar ---------------------------------------------------------------
LOOKBACK_DAYS = 120        # kaç günlük mailler taransın (~4 ay)
WINDOW_DAYS = 30           # deadline'ı kaç gün içinde olanlar gösterilsin
BATCH_SIZE = 25            # Claude'a tek seferde gönderilecek mail sayısı
MODEL = "opus"            # Claude hesabındaki en güncel Opus modeli
# ---------------------------------------------------------------------------

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
STATE_FILE = DATA / "state.json"
OUT_FILE = DATA / "deadlines.json"
LOCK_FILE = DATA / ".lock"
FETCH_JS = BASE / "fetch_mail.js"

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
AYNI title'ı birebir kullan.
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


class ClaudeNotLoggedIn(Exception):
    pass


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


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed": {}}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
    tmp.replace(STATE_FILE)


def fetch_new_mails(known_ids, limit):
    known_file = DATA / ".known_ids.json"
    known_file.write_text(json.dumps(list(known_ids)))
    out = subprocess.run(
        ["osascript", "-l", "JavaScript", str(FETCH_JS), str(LOOKBACK_DAYS), str(known_file), str(limit)],
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
    found = ask_claude(SYSTEM, "\n".join(parts), SCHEMA, "low")["deadlines"]
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

MERGE_SYSTEM = """Sana bir öğrencinin maillerinden çıkarılmış gelecekteki deadline listesi verilecek. \
Bazıları AYNI işin tekrarı olabilir: farklı yazılmış başlıklar, hatırlatma mailleri, ya da hocanın \
sonradan uzattığı/değiştirdiği tarihler. Aynı işe ait kayıtları grupla; her grupta SADECE en son \
gönderilen maildeki (mail_date en yeni) tarihi tut, diğerlerini "drop" listesine koy. Farklı işleri \
(örn. Project 1 ve Project 2, ya da farklı dersler) asla birleştirme. Emin değilsen bırakma."""


def merge_duplicates(state):
    """Uzatma/tekrar kayıtlarını Claude ile ayıkla; sonucu state['dropped'] içine yazar."""
    today = dt.date.today().isoformat()
    items = sorted((d for d in all_deadlines(state) if d["deadline_date"] >= today),
                   key=lambda d: d["deadline_date"])
    if len(items) < 2:
        state["dropped"] = []
        return
    lines = [f"[{i}] {d['title']} | tarih: {d['deadline_date']} {d['deadline_time']} | "
             f"kaynak: {d['source']} | mail: \"{d['mail_subject']}\" ({d['mail_date'][:10]})"
             for i, d in enumerate(items)]
    try:
        result = ask_claude(MERGE_SYSTEM, "\n".join(lines), MERGE_SCHEMA, "medium")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="Mail okumadan sadece listeyi yenile")
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    lock = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("Başka bir tarama zaten çalışıyor, çıkılıyor.")
        return

    state = load_state()
    if args.rebuild:
        log(f"{len(write_output(state))} deadline yazıldı.")
        return

    found_any = False
    while True:
        res = fetch_new_mails(state["processed"].keys(), BATCH_SIZE)
        mails = res["messages"]
        if not mails:
            break
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

    if found_any or "dropped" not in state:
        log("Tekrarlar ve uzatmalar kontrol ediliyor...")
        merge_duplicates(state)
        save_state(state)
    items = write_output(state)
    log(f"Bitti. Önümüzdeki {WINDOW_DAYS} günde {len(items)} deadline var.")


if __name__ == "__main__":
    try:
        main()
    except ClaudeNotLoggedIn:
        log("HATA: Claude girişi yok. Terminalde 'claude auth login' çalıştır.")
        sys.exit(1)
