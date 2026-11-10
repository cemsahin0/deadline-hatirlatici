# 📌 Deadline Hatırlatıcı

Apple Mail'deki son ~4 ayın maillerini okur, içlerindeki son tarihleri Claude ile bulur
ve **30 gün ya da daha az kalanları** masaüstünde sarı bir post-it'te gösterir.

## Kurulum (her Mac için)

**Gerekenler:** Mail uygulamasında kurulu bir mail hesabı ve bir Claude aboneliği.

1. **Claude Code'u kur ve giriş yap** (zaten varsa bu adımı geç). Terminal'i aç:
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```
   ```bash
   claude auth login
   ```
   Açılan tarayıcıda kendi Claude hesabınla izin ver. Ayrı ücret yok, aboneliğinin kullanım hakkından gider.

2. **İndir ve kur:**
   ```bash
   git clone https://github.com/cemsahin0/deadline-hatirlatici.git ~/Documents/deadline-hatirlatici && bash ~/Documents/deadline-hatirlatici/install.sh
   ```
   (git sorarsa GitHub'a giriş yap. Alternatif: GitHub sayfasında **Code → Download ZIP**,
   klasörü Belgeler'e taşı, Terminal'de `bash ~/Documents/deadline-hatirlatici-main/install.sh`.)

3. macOS "Python, Belgeler klasörüne / Mail'e erişmek istiyor" diye sorarsa → **İzin Ver**.

`install.sh` eksik bir şey varsa (Python, Claude Code, giriş) ne yapman gerektiğini söyler;
düzeltip tekrar çalıştırman yeterli.

İlk tarama mail sayısına göre 1-1,5 saat sürer, çünkü Mail her mailin içeriğini yavaş veriyor.
Post-it bu sırada kademeli olarak dolar. Sonraki taramalar sadece yeni mailleri okur.

## Güncelleme

Kodda bir değişiklik GitHub'a gönderildiğinde, kurulu her bilgisayarda:
```bash
cd ~/Documents/deadline-hatirlatici && git pull && bash install.sh
```
Kayıtlar (bulunan deadline'lar, tamamlananlar, post-it'in yeri ve boyutu) korunur.

## Arkadaşınla paylaşma

Repo private olduğu için arkadaşın önce eklenmeli:
1. GitHub'da repo sayfası → **Settings → Collaborators → Add people** → arkadaşının GitHub kullanıcı adı.
2. Arkadaşın gelen daveti kabul eder.
3. Yukarıdaki **Kurulum** adımlarını kendi Mac'inde uygular.

Her bilgisayar **kendi** mailini okur ve **kendi** Claude hesabını kullanır; kimsenin
kullanım hakkı birbirinden gitmez. Herkesin deadline'ları kendi `data/` klasöründe durur,
repoya hiç gönderilmez (`.gitignore`), yani kimse başkasının maillerini görmez.


## Kullanım

Post-it masaüstüne yapışıktır: uygulamaların altında kalır, tüm masaüstlerinde görünür.
Mac her açıldığında kendiliğinden gelir; kayıtlar `data/` klasöründe saklanır.

| | |
|---|---|
| **Renkler** | kırmızı ≤ 3 gün · turuncu ≤ 7 gün · yeşil ≤ 30 gün |
| **✓** | işi bitirdin: listenin en altındaki "Tamamlananlar"a taşır (↺ ile geri al) |
| **Çift tık** | deadline'ın kaynağını açar (mail, ders sitesi ya da dosya) |
| **Sürükle** | notu istediğin yere taşı (yeri hatırlanır) |
| **◢ (sağ alt köşe)** | sürükleyerek boyutunu ayarla (boyut hatırlanır) |
| **–** | notu tek satıra küçültür ("4 deadline · 1 acil!") |
| **🔗** | ders sitesi ekle (bkz. Ders siteleri) |
| **📎** | PDF / Word dosyası ekle (bkz. PDF ve Word dosyaları) |
| **⟳** | mailleri hemen tarar (normalde açılışta ve her 10 dakikada bir) |
| **Sağ tık** | menü: kendim ekle (gizli), şimdi tara, site/dosya ekle, yönet, gizlilik ayarı, bitti işaretlenenleri geri getir, kapat |

## PDF ve Word dosyaları

Syllabus, ödev açıklaması gibi bir dosyadaki tarihleri de ekleyebilirsin:

1. Post-it'in üstündeki **📎** butonuna bas.
2. Açılan pencerede dosyayı seç (İndirilenler'den açılır; soldan Masaüstü vb. de seçebilirsin,
   **Cmd** basılı tutarak birden fazla dosya seçebilirsin) → **Aç**.
3. Birkaç saniye içinde bildirim gelir: kaç yaklaşan tarih bulunduğunu, dosyada tarih yoksa
   "Burada bir deadline / yaklaşan tarih bulunamadı", tarihler geçmişse "hepsi geçmiş" der.

Okunabilenler: **PDF, Word (.docx, .doc), .rtf, .odt, .txt**. Taranmış (fotoğraf) PDF'lerde yazı
olmadığı için okunamaz; bildirim bunu söyler. İlk seferde macOS "İndirilenler klasörüne erişim"
izni sorarsa **İzin Ver** de. Dosyadan gelen bir deadline'a çift tıklarsan dosya açılır.
Ders sitesinde bir PDF linki varsa onu da 🔗 ile site gibi ekleyebilirsin.

## Ders siteleri

Bazı hocalar duyuruları mail yerine kendi web sitesine koyuyor. Onları da eklemek çok kolay:

1. Tarayıcıda dersin sayfasını aç, üstteki adres çubuğuna tıkla ve **Cmd+C** ile kopyala.
2. Post-it'in üstündeki **🔗** butonuna bas.
3. Açılan pencereye **Cmd+V** ile yapıştır ve **Ekle** de.

Birkaç saniye içinde sağ üstte bir bildirim gelir: kaç tarih bulunduğunu ya da neden
okunamadığını (link yanlış, sayfa şifreli vb.) ve ne yapman gerektiğini söyler.
Siteyi çıkarmak için: post-it'e **sağ tık → Siteleri, dosyaları, notları yönet…** → siteyi seç → **Seçilenleri kaldır**.

Eklediğin siteler sadece senin bilgisayarında durur (`data/sites.txt`), GitHub'a gönderilmez.

Siteye zarar vermemek için:
- Her site en fazla **6 saatte bir**, tek bir sayfa isteğiyle okunur (günde ~4 istek; linkler takip edilmez).
- Sayfa değişmediyse sunucu içeriği tekrar göndermez (ETag / Last-Modified), Claude'a da sorulmaz.
- Site `robots.txt` ile bu tür araçları engelliyorsa okunmaz.

Not: Sadece şifresiz açılan normal web sayfaları okunabilir (SUCourse gibi giriş gerektiren
sayfalar okunamaz). Sitedeki PDF / Word linkleri de eklenebilir.

Hocanın sonradan uzattığı/değiştirdiği tarihler otomatik güncellenir: mailler eskiden yeniye
okunur, en son duyurulan tarih geçerli olur, iptal edilenler listeden düşer. Her taramanın
sonunda aynı işin tekrar eden kayıtları da ayıklanır.

## Gizlilik: verilerin nereye gidiyor?

- **Program senin Mac'inde çalışır.** Mailleri okuma, tarihe göre süzme, post-it'i çizme, siteleri
  kontrol etme gibi işleri bu klasördeki kod yapar. Başka bir sunucu yok.
- **Claude'a giden kısım:** Bir mailin, sitenin ya da dosyanın *içinde deadline olup olmadığını
  anlamak* ve aynı işin tekrarlarını birleştirmek için o metin, **senin Claude hesabın üzerinden
  Anthropic'e** (Claude'u yapan şirket) gönderilir. Bu, claude.ai'da bir mesaj yazmakla aynıdır;
  hesabının gizlilik ayarları geçerlidir. Sohbetlerinin model eğitiminde kullanılmasını istemiyorsan
  claude.ai → **Ayarlar → Gizlilik** kısmından kapatabilirsin.
- Sadece **yeni** mailler gönderilir; bir kez işlenen mail tekrar gönderilmez.
- **Hangi mailler gönderilsin?** Post-it'e sağ tık → **Hangi mailler okunsun? (gizlilik)…** ile
  izinli göndericileri yaz (örn. `@sabanciuniv.edu`). Listede olmayan maillerin konusu ve içeriği
  **hiç okunmaz**, hiçbir yere gönderilmez. Alt alan adları da sayılır (`sucourse.sabanciuniv.edu`).
  Boş bırakırsan tüm mailler gönderilir.
- **Gizli bir iş mi var?** Sağ tık → **🔒 Kendim ekle (gizli)…** → ne yapacağını ve tarihi yaz
  (`25.11`, `25.11.2026 23:59`, `25 Kasım 14:00`, `yarın`). Bu not sadece bu Mac'te
  (`data/manual.json`) durur, Claude dahil hiçbir yere gönderilmez; post-it'te diğerleri gibi görünür.
  Çift tıklayınca silebilirsin.
- **GitHub'a giden:** sadece kod. `data/` klasörü (mail başlıkları, deadline'lar, eklediğin
  siteler/dosyalar) asla gönderilmez.
- **iCloud:** Belgeler klasörün iCloud ile senkronize ediliyorsa `data/` klasörü de (diğer
  belgelerin gibi) kendi iCloud hesabına yedeklenir. Python ortamı bu yüzden iCloud dışında,
  `~/Library/Application Support/Deadline Hatirlatici/` içinde durur.

## Ayarlar

`deadline_reminder.py` dosyasının başında:
- `LOOKBACK_DAYS = 120` — kaç günlük mail taransın
- `WINDOW_DAYS = 30` — kaç gün kalanlar gösterilsin
- `MODEL` — kullanılan Claude modeli

## Kullanım hakkı

Claude hesabın üzerinden çalışır, ayrı ödeme yok. İlk tarama (~800 mail, ~35 istek) kullanım
hakkından bir miktar yer; sonraki taramalar çok küçük. Hakkın çabuk doluyorsa
`MODEL = "sonnet"` yapabilirsin.

## Kaldırma

`bash uninstall.sh` otomatik çalıştırmayı kapatır. Kayıtlar `data/` klasöründe durur.
