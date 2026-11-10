"""Ders web sitelerini siteyi yormadan kontrol eder.

- Her site en fazla CHECK_EVERY_H saatte bir, tek bir sayfa isteğiyle okunur (link takibi yok).
- Koşullu istek (ETag / Last-Modified) gönderilir: sayfa değişmediyse içerik hiç inmez.
- robots.txt bu aracı engelliyorsa site okunmaz.
- Sayfa metni değişmediyse Claude'a tekrar sorulmaz (token harcanmaz).

Site listesi: data/sites.txt (her satıra bir link, # ile başlayan satırlar yok sayılır).
"""
import datetime as dt
import hashlib
import socket
import subprocess
import html.parser
import ssl
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

UA = "DeadlineHatirlatici/1.0 (kisisel ders takvimi hatirlaticisi; birkac saatte bir tek istek)"
CHECK_EVERY_H = 6

try:  # python.org Python kendi sertifika listesini getirmiyor; certifi'ninkini kullan
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()
TIMEOUT = 20
MAX_BYTES = 3_000_000
MAX_CHARS = 40_000

PAGE_NOTE = ("(Bu bir mail DEĞİL: dersin web sayfasının şu anki içeriği. Sadece öğrencinin yapması "
             "gereken teslim, sınav, quiz, proje, başvuru tarihlerini al; ders konu başlıklarını ve "
             "slayt tarihlerini alma. Sayfada yıl yazmıyorsa en yakın mantıklı yılı kullan. "
             "Sayfa en güncel bilgidir: tarih burada değiştiyse yeni tarihi yaz.)\n\n")

_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section",
          "article", "header", "footer", "ul", "ol", "dt", "dd", "pre", "hr"}


class _Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.title, self._skip, self._in_title = [], "", 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.out.append(data)


def html_to_text(raw):
    p = _Text()
    p.feed(raw)
    lines = (" ".join(l.split()) for l in "".join(p.out).splitlines())
    text = "\n".join(l for l in lines if l.strip(" |"))
    return " ".join(p.title.split()), text


def read_site_list(path):
    if not path.exists():
        return []
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line.startswith(("http://", "https://")):
            if line not in urls:
                urls.append(line)
    return urls


def robots_allows(url):
    """robots.txt bu aracı engelliyor mu? Dosya yoksa izinli; ağ hatası olursa hata fırlatır."""
    u = urllib.parse.urlsplit(url)
    robots = f"{u.scheme}://{u.netloc}/robots.txt"
    try:
        req = urllib.request.Request(robots, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
            body = r.read(500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code not in (401, 403)   # robots.txt yok (404 vb.) → izinli
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    return rp.can_fetch(UA, url)


def fetch(url, meta):
    """(durum, title, metin, yeni_meta). durum: 'changed' | 'same' | 'login' | 'unsupported'."""
    headers = {"User-Agent": UA, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
            ctype = r.headers.get("Content-Type", "")
            if not any(t in ctype for t in ("html", "text/plain", "xml")) and ctype:
                return "unsupported", "", ctype, meta
            raw = r.read(MAX_BYTES)
            charset = r.headers.get_content_charset() or "utf-8"
            new_meta = {**meta, "etag": r.headers.get("ETag", ""),
                        "last_modified": r.headers.get("Last-Modified", "")}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return "same", "", "", meta
        raise
    text_raw = raw.decode(charset, "replace")
    low = text_raw.lower()
    if 'type="password"' in low or "type='password'" in low or "type=password" in low:
        return "login", "", "", meta
    if "html" in ctype or "<html" in text_raw[:2000].lower():
        title, text = html_to_text(text_raw)
    else:
        title, text = "", text_raw
    digest = hashlib.sha256(text.encode()).hexdigest()
    status = "same" if digest == meta.get("hash") else "changed"
    new_meta["hash"] = digest
    return status, title, text, new_meta


def notify(title, message):
    """macOS bildirimi göster (site eklendikten sonra sonucu kullanıcıya söylemek için)."""
    try:
        subprocess.run(["osascript", "-e", "on run argv", "-e",
                        "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run", title, message], timeout=10, capture_output=True)
    except Exception:
        pass


def friendly_error(e):
    """Hata mesajını teknik olmayan, ne yapılacağını söyleyen bir cümleye çevir."""
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (401, 403):
            return "Site giriş istiyor ya da erişime kapalı. Sadece herkese açık sayfalar okunabilir."
        if e.code == 404:
            return "Sayfa bulunamadı. Linki tarayıcıda açıp adres çubuğundan tekrar kopyala."
        return f"Site hata verdi (kod {e.code}). Daha sonra tekrar denenecek."
    reason = getattr(e, "reason", e)
    if isinstance(reason, socket.gaierror):
        return "Siteye ulaşılamadı: link yanlış olabilir ya da internet yok."
    if isinstance(reason, (TimeoutError, socket.timeout)) or isinstance(e, (TimeoutError, socket.timeout)):
        return "Site yanıt vermedi. Daha sonra tekrar denenecek."
    return f"Site okunamadı ({reason}). Daha sonra tekrar denenecek."


def due(meta, now):
    last = meta.get("checked")
    if not last:
        return True
    return now - dt.datetime.fromisoformat(last) >= dt.timedelta(hours=CHECK_EVERY_H)


def check_sites(state, sites_file, extract, log, force=False):
    """Zamanı gelen siteleri okur; değişmişse deadline'larını state['processed'] içine yazar.
    True döner: en az bir sitenin deadline'ları güncellendiyse."""
    urls = read_site_list(sites_file)
    metas = state.setdefault("sites", {})
    # Listeden silinen sitelerin kayıtlarını kaldır
    for key in [k for k in state["processed"] if k.startswith("site:") and k[5:] not in urls]:
        del state["processed"][key]
    for url in [u for u in metas if u not in urls]:
        del metas[url]

    changed_any = False
    now = dt.datetime.now()
    for url in urls:
        meta = metas.get(url, {})
        if not force and not due(meta, now):
            continue
        host = urllib.parse.urlsplit(url).netloc
        first = not meta.get("checked")   # yeni eklendi: sonucu bildirimle söyle
        say = (lambda msg: notify(f"Ders sitesi: {host}", msg)) if first else (lambda msg: None)
        try:
            if first and not robots_allows(url):
                log(f"Site atlandı (robots.txt izin vermiyor): {url}")
                say("Bu site otomatik okunmak istemiyor (robots.txt). Deadline'ları buradan alınamaz.")
                metas[url] = {**meta, "checked": now.isoformat(timespec="seconds"), "blocked": True}
                continue
            if meta.get("blocked"):
                continue
            status, title, text, new_meta = fetch(url, meta)
        except Exception as e:
            log(f"Site okunamadı ({host}): {e}")
            say(friendly_error(e))
            metas[url] = {**meta, "checked": now.isoformat(timespec="seconds")}
            continue
        new_meta["checked"] = now.isoformat(timespec="seconds")
        if status in ("unsupported", "login"):
            msg = ("Bu sayfa giriş (şifre) istiyor; sadece herkese açık sayfalar okunabilir."
                   if status == "login" else
                   "Bu link bir web sayfası değil (PDF ya da dosya). Dersin ana sayfasının linkini ekle.")
            log(f"Site atlandı ({host}): {msg}")
            say(msg)
            metas[url] = new_meta
            continue
        if status == "same" and f"site:{url}" in state["processed"]:
            metas[url] = new_meta
            continue
        log(f"Ders sitesi okunuyor: {title or host}")
        page = {"id": f"site:{url}", "sender": host,
                "date": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "subject": title or url, "content": PAGE_NOTE + text[:MAX_CHARS]}
        found = extract([page], state)
        state["processed"][page["id"]] = {
            "subject": page["subject"], "sender": host, "date": page["date"], "url": url,
            "deadlines": [{k: d[k] for k in ("title", "deadline_date", "deadline_time", "source", "status")}
                          for d in found],
        }
        metas[url] = new_meta  # sadece başarıyla işlendiyse kaydet
        changed_any = True
        for d in found:
            log(f"  + {d['deadline_date']} {d['title']}  (site)")
        today = dt.date.today().isoformat()
        upcoming = [d for d in found if d["deadline_date"] >= today and d.get("status") != "cancelled"]
        if upcoming:
            say(f"Eklendi ✓ {len(upcoming)} yaklaşan tarih bulundu, post-it'e eklendi. "
                "Site birkaç saatte bir kontrol edilecek.")
        else:
            say("Eklendi ✓ Şu an yaklaşan bir tarih yok; sayfa değişirse otomatik görünecek.")
    return changed_any
