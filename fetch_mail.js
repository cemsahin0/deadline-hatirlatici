// Apple Mail'deki gelen kutusundan son N günün maillerini okur (JXA).
// Kullanım: osascript -l JavaScript fetch_mail.js <gun_sayisi> <bilinen_idler_dosyasi> [max_yeni] [izinli_gondericiler.json]
// Çıktı: JSON -> [{id, subject, sender, date, content}]  (sadece daha önce işlenmemiş mailler)
// İzinli gönderici listesi verilmişse, listede olmayanların İÇERİĞİ OKUNMAZ: {id, sender, date, skipped:true}
ObjC.import('Foundation');

function readFile(path) {
  const s = $.NSString.stringWithContentsOfFileEncodingError(path, $.NSUTF8StringEncoding, null);
  return s.isNil() ? '' : ObjC.unwrap(s);
}

// "@okul.edu" → okul.edu ve alt alan adları (sucourse.okul.edu); "kisi@x.com" → tam adres
function senderAllowed(sender, patterns) {
  if (!patterns.length) return true;
  const m = String(sender || '').toLowerCase().match(/<([^>]+)>/);
  const addr = (m ? m[1] : String(sender || '')).trim().toLowerCase();
  return patterns.some(p => {
    p = p.trim().toLowerCase();
    if (!p) return false;
    if (!p.startsWith('@') && !p.includes('@')) p = '@' + p;
    if (p.startsWith('@')) return addr.endsWith(p) || addr.endsWith('.' + p.slice(1));
    return addr === p;
  });
}

function run(argv) {
  const days = parseInt(argv[0] || '120', 10);
  const known = new Set(JSON.parse(readFile(argv[1] || '/dev/null') || '[]').map(String));
  const maxNew = parseInt(argv[2] || '400', 10);
  const allowed = argv[3] ? (JSON.parse(readFile(argv[3]) || '[]') || []) : [];

  const Mail = Application('Mail');
  const cutoff = new Date(Date.now() - days * 86400 * 1000);
  // Not: "whose" filtresi binlerce mailde çok yavaş; toplu okuyup burada filtreliyoruz.
  const msgs = Mail.inbox.messages;
  const ids = msgs.id();
  const subjects = msgs.subject();
  const senders = msgs.sender();
  const dates = msgs.dateReceived();

  // Eskiden yeniye sırala: önce ilk duyuru, sonra uzatma/değişiklik maili işlensin.
  const order = [];
  for (let i = 0; i < ids.length; i++) {
    if (dates[i] && dates[i] >= cutoff) order.push(i);
  }
  order.sort((a, b) => dates[a] - dates[b]);
  const inRange = order.length;

  const out = [];
  for (const i of order) {
    if (out.filter(m => !m.skipped).length >= maxNew) break;
    const id = String(ids[i]);
    if (known.has(id)) continue;
    if (!senderAllowed(senders[i], allowed)) {   // gizli: içeriğe hiç dokunma
      out.push({ id: id, sender: senders[i] || '', date: dates[i] ? dates[i].toISOString() : '', skipped: true });
      continue;
    }
    let content = '';
    try { content = msgs[i].content() || ''; } catch (e) { content = ''; }
    out.push({
      id: id,
      subject: subjects[i] || '',
      sender: senders[i] || '',
      date: dates[i] ? dates[i].toISOString() : '',
      content: content.slice(0, 6000),
    });
  }
  return JSON.stringify({ total_in_range: inRange, messages: out });
}
