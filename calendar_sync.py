"""Deadline'ları Mac'teki Takvim uygulamasına, ayrı bir "Deadline'lar" takvimine yazar.

- Sadece değişiklik varsa Takvim'e dokunur (her taramada değişmeyen liste için hiçbir şey yapmaz).
- Tarih değişirse (uzatma) etkinlik güncellenir; iptal edilen / birleştirilen / ✓ ile bitirilen iş
  takvimden silinir. Tarihi geçmiş etkinliklere dokunulmaz (geçmiş kayıt olarak kalır).
- Saatli deadline: o saatte biten 30 dk'lık etkinlik, 1 gün ve 2 saat önce uyarı.
  Saatsiz deadline: tüm gün etkinlik, 1 gün önce uyarı.
- Takvim'le konuşmak için AppleScript (osascript) kullanılır; ilk seferde macOS izin sorar.
"""
import datetime as dt
import hashlib
import json
import subprocess

CAL_NAME = "Deadline'lar"

_JXA = r"""
function run(argv) {
  const job = JSON.parse(argv[0]);
  const C = Application('Calendar');
  let cals = C.calendars.whose({name: job.calName})();
  let recreated = false;
  let cal;
  if (cals.length) { cal = cals[0]; }
  else { cal = C.Calendar({name: job.calName}); C.calendars.push(cal); cal = C.calendars.whose({name: job.calName})()[0]; recreated = true; }
  const find = uid => { if (!uid) return null; const r = cal.events.whose({uid: uid})(); return r.length ? r[0] : null; };
  const out = {recreated: recreated, uids: {}, errors: []};
  for (const uid of job.remove) { try { const e = find(uid); if (e) C.delete(e); } catch (x) { out.errors.push(String(x)); } }
  for (const ev of job.upsert) {
    try {
      // Değişen etkinliği silip yeniden oluştur (yerinde güncelleme uyarıları çoğaltıyor)
      const old = recreated ? null : find(ev.uid);
      if (old) C.delete(old);
      const e = C.make({new: 'event', at: cal, withProperties: {summary: ev.summary,
        startDate: new Date(ev.start), endDate: new Date(ev.end), alldayEvent: ev.allday, description: ev.notes}});
      for (const m of ev.alarms) e.displayAlarms.push(C.DisplayAlarm({triggerInterval: m}));
      out.uids[ev.key] = e.uid();
    } catch (x) { out.errors.push(ev.summary + ': ' + String(x)); }
  }
  return JSON.stringify(out);
}
"""


def _event_for(d):
    day = dt.date.fromisoformat(d["deadline_date"])
    t = d.get("deadline_time") or ""
    notes = f"Kaynak: {d.get('source', '')}\nDeadline Hatırlatıcı tarafından eklendi."
    if t:
        h, m = map(int, t.split(":"))
        end = dt.datetime.combine(day, dt.time(h, m))
        start = end - dt.timedelta(minutes=30)
        return {"summary": f"⏰ {d['title']}", "start": start.isoformat(), "end": end.isoformat(),
                "allday": False, "notes": notes, "alarms": [-1440, -120]}
    # Tüm gün etkinlik: bitiş = başlangıç (Takvim, ertesi gün 00:00'ı iki günlük etkinlik sayıyor)
    midnight = dt.datetime.combine(day, dt.time()).isoformat()
    return {"summary": f"⏰ {d['title']}", "start": midnight, "end": midnight,
            "allday": True, "notes": notes, "alarms": [-1440 + 9 * 60]}   # bir önceki gün 09:00


def _sig(ev):
    return hashlib.sha1(json.dumps(ev, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sync(items, map_file, log, cal_name=CAL_NAME):
    """items: takvimde olması gereken deadline'lar (gelecek, aktif, bitirilmemiş).
    map_file: anahtar → {uid, sig, date} eşlemesinin tutulduğu JSON dosyası."""
    try:
        mapping = json.loads(map_file.read_text())
    except Exception:
        mapping = {}
    today = dt.date.today().isoformat()

    want = {}
    for d in items:
        key = d["title"].strip().lower()
        ev = _event_for(d)
        want[key] = {**ev, "key": key, "date": d["deadline_date"]}

    upsert, remove = [], []
    for key, ev in want.items():
        old = mapping.get(key)
        if not old or old.get("sig") != _sig(ev):
            upsert.append({**ev, "uid": (old or {}).get("uid", "")})
    for key, old in mapping.items():
        if key not in want and old.get("date", "") >= today:
            remove.append(old.get("uid", ""))
    # Tarihi geçmiş eşlemeleri unut (etkinlik takvimde geçmiş kayıt olarak kalır)
    mapping = {k: v for k, v in mapping.items() if k in want}

    if not upsert and not remove:
        return 0
    job = {"calName": cal_name, "upsert": upsert, "remove": [u for u in remove if u]}
    out = subprocess.run(["osascript", "-l", "JavaScript", "-e", _JXA, json.dumps(job, ensure_ascii=False)],
                         capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        log(f"Takvime yazılamadı: {out.stderr.strip()[:300]}")
        return 0
    res = json.loads(out.stdout)
    if res.get("recreated"):
        # Takvim yoktu (ilk sefer ya da kullanıcı sildi): eşleme sıfırdan
        mapping = {k: v for k, v in mapping.items() if k in res["uids"]}
    for ev in upsert:
        uid = res["uids"].get(ev["key"])
        if uid:
            mapping[ev["key"]] = {"uid": uid, "sig": _sig({k: ev[k] for k in ev if k not in ("uid",)}),
                                  "date": ev["date"]}
    for e in res.get("errors", []):
        log(f"Takvim hatası: {e}")
    map_file.write_text(json.dumps(mapping, ensure_ascii=False, indent=1))
    if res.get("recreated") and any(k not in res["uids"] for k in want):
        return sync(items, map_file, log, cal_name)   # takvim yeni açıldıysa eksik kalanları da ekle
    log(f"Takvim güncellendi: {len(res['uids'])} etkinlik eklendi/değişti, {len(job['remove'])} silindi")
    return len(res["uids"]) + len(job["remove"])
