# 📌 Deadline Hatırlatıcı

Apple Mail'deki son ~4 ayın maillerini okur, içlerindeki son tarihleri yapay zekâyla
(**Claude** ya da **ChatGPT/Codex**, hangisi varsa) bulur ve **30 gün ya da daha az kalanları**
masaüstünde sarı bir post-it'te gösterir.

## Kurulum (her Mac için, ~10 dakika)

**Gerekenler:**
- Bir **Mac**
- Okul mailinin **Mail** uygulamasında ekli olması (Sistem Ayarları → İnternet Hesapları)
- **Claude** (Pro/Max) ya da **ChatGPT** (Plus/Pro) aboneliğinden biri

Aşağıdaki komutları **Terminal**'e yapıştırıp Enter'a basacaksın. Terminal'i açmak için
**Cmd + Boşluk** → `Terminal` yaz → Enter.

### 1. Yapay zekâ aracını kur (hangi aboneliğin varsa sadece onu yap)

**A) Claude aboneliğin varsa:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```
```bash
claude auth login
```

**B) ChatGPT aboneliğin varsa (Codex):**
```bash
brew install --cask codex
```
(`brew` yoksa: önce [nodejs.org](https://nodejs.org)'dan Node.js'i kur, sonra `npm install -g @openai/codex`)
```bash
codex login
```

Giriş komutu tarayıcıyı açar; kendi hesabınla giriş yapıp izin ver. Ayrı ücret yok,
aboneliğinin kullanım hakkından gider. İkisi de kuruluysa Claude kullanılır.

### 2. Python'u kur

[python.org/downloads](https://www.python.org/downloads/) → sarı **Download Python** düğmesi → inen
dosyayı açıp kur. (Mac'teki hazır Python post-it için yetmiyor. Zaten kurduysan geç.)

### 3. İndir ve kur

```bash
git clone https://github.com/cemsahin0/deadline-hatirlatici.git ~/Documents/deadline-hatirlatici && bash ~/Documents/deadline-hatirlatici/install.sh
```
Mac "geliştirici araçlarını yükle" diye sorarsa **Yükle** de, bitince komutu tekrar yapıştır.

`install.sh` eksik bir şey varsa (Python, Claude/Codex, giriş) ne yapman gerektiğini yazıp durur;
söyleneni yapıp aynı komutu tekrar çalıştırman yeterli. Sonunda **"Kuruldu!"** yazar.

### 4. İzinler ve ilk ayar

- macOS "Mail'i / Takvim'i / Belgeler klasörünü kontrol etmek istiyor" diye sorarsa → **İzin Ver**.
- Masaüstüne sarı post-it gelir ve **hangi maillerin okunacağını** sorar. Okulunun mail uzantısını yaz:
  `@sabanciuniv.edu` (birden fazlaysa virgülle: `@sabanciuniv.edu, hoca.adi@gmail.com`).
  **Bunu seçmeden hiçbir mail okunmaz.**

İlk tarama mail sayısına göre 30 dk – 1,5 saat sürer, çünkü Mail her mailin içeriğini yavaş veriyor.
Post-it bu sırada kademeli olarak dolar. Sonraki taramalar sadece yeni mailleri okur.

## Güncelleme

Kodda bir değişiklik GitHub'a gönderildiğinde, kurulu her bilgisayarda:
```bash
cd ~/Documents/deadline-hatirlatici && git pull && bash install.sh
```
Kayıtlar (bulunan deadline'lar, tamamlananlar, post-it'in yeri ve boyutu) korunur.

## Arkadaşınla paylaşma

Repo linkini göndermen yeterli: https://github.com/cemsahin0/deadline-hatirlatici
Arkadaşın yukarıdaki **Kurulum** adımlarını kendi Mac'inde uygular.

Her bilgisayar **kendi** mailini okur ve **kendi** Claude/ChatGPT hesabını kullanır; kimsenin
kullanım hakkı birbirinden gitmez. Herkesin deadline'ları, ayarları, eklediği siteler ve notlar kendi
bilgisayarındaki kayıt klasöründe durur, repoya hiç gönderilmez (`.gitignore`), yani kimse
başkasının maillerini görmez.

## Kullanım

Post-it masaüstüne yapışıktır: uygulamaların altında kalır, tüm masaüstlerinde görünür.
Mac her açıldığında kendiliğinden gelir; kayıtlar bilgisayarında saklanır (bkz. **Dosyalar nerede?**).

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
| **Sağ tık** | menü: kendim ekle (gizli), şimdi tara, site/dosya ekle, yönet, gizlilik ayarı, takvime ekle, bitti işaretlenenleri geri getir, kapat |

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

## Mac Takvimi

Post-it'e sağ tık → **📅 Mac Takvimine ekle** işaretlersen deadline'lar Takvim uygulamasında ayrı bir
**"Deadline'lar"** takvimine eklenir (iCloud takvimin varsa iPhone'unda da görünür).

- Saatli deadline: o saatte biten etkinlik, **1 gün ve 2 saat önce** uyarı. Saatsiz: tüm gün
  etkinlik, **bir önceki gün 09:00**'da uyarı.
- Sadece post-it'teki 30 gün değil, bilinen **tüm gelecek** deadline'lar eklenir.
- Hoca tarihi uzatırsa etkinlik de taşınır; iptal edilen, birleştirilen ya da ✓ ile bitirdiğin iş
  takvimden silinir. Geçmiş etkinliklere dokunulmaz.
- Takvim'e sadece değişiklik olduğunda yazılır. İlk seferde macOS "Takvim'i kontrol etme" izni
  sorarsa **İzin Ver** de.
- Kapatırsan eklenmiş etkinlikler kalır; istersen Takvim'de "Deadline'lar"a sağ tık → **Sil**.

## Ders siteleri

Bazı hocalar duyuruları mail yerine kendi web sitesine koyuyor. Onları da eklemek çok kolay:

1. Tarayıcıda dersin sayfasını aç, üstteki adres çubuğuna tıkla ve **Cmd+C** ile kopyala.
2. Post-it'in üstündeki **🔗** butonuna bas.
3. Açılan pencereye **Cmd+V** ile yapıştır ve **Ekle** de.

Birkaç saniye içinde sağ üstte bir bildirim gelir: kaç tarih bulunduğunu ya da neden
okunamadığını (link yanlış, sayfa şifreli vb.) ve ne yapman gerektiğini söyler.
Siteyi çıkarmak için: post-it'e **sağ tık → Siteleri, dosyaları, notları yönet…** → siteyi seç → **Seçilenleri kaldır**.

Eklediğin siteler sadece senin bilgisayarında durur (kayıt klasöründe `sites.txt`), GitHub'a gönderilmez.

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
- **Yapay zekâya giden kısım:** Bir mailin, sitenin ya da dosyanın *içinde deadline olup olmadığını
  anlamak* ve aynı işin tekrarlarını birleştirmek için o metin **senin hesabın üzerinden** gönderilir:
  Claude kullanıyorsan **Anthropic'e**, Codex kullanıyorsan **OpenAI'a**. Bu, claude.ai'da ya da
  ChatGPT'de bir mesaj yazmakla aynıdır; hesabının gizlilik ayarları geçerlidir. Model eğitiminde
  kullanılmasını istemiyorsan claude.ai → **Ayarlar → Gizlilik** ya da ChatGPT → **Ayarlar → Veri
  kontrolleri** kısmından kapatabilirsin.
- Sadece **yeni** mailler gönderilir; bir kez işlenen mail tekrar gönderilmez.
- **Hangi mailler gönderilsin?** Post-it'e sağ tık → **Hangi mailler okunsun? (gizlilik)…** ile
  izinli göndericileri yaz (örn. `@sabanciuniv.edu`). Listede olmayan maillerin konusu ve içeriği
  **hiç okunmaz**, hiçbir yere gönderilmez. Alt alan adları da sayılır (`sucourse.sabanciuniv.edu`).
  Kurulumdan sonra post-it bunu ilk açılışta kendisi sorar; seçilene kadar hiçbir mail okunmaz.
- **Gizli bir iş mi var?** Sağ tık → **🔒 Kendim ekle (gizli)…** → ne yapacağını ve tarihi yaz
  (`25.11`, `25.11.2026 23:59`, `25 Kasım 14:00`, `yarın`). Bu not sadece bu Mac'te
  (kayıt klasöründe `manual.json`) durur, yapay zekâ dahil hiçbir yere gönderilmez; post-it'te diğerleri gibi görünür.
  Çift tıklayınca silebilirsin.
- **Her hafta tekrar eden bir iş mi?** (haftalık ödev, lab raporu…) "Kendim ekle"nin son adımında
  **Her hafta tekrarla** de. Bir kere eklersin; ✓ ile bitirince bir sonraki haftaya geçer, bitirmeden
  tarihi geçerse de sıradaki hafta gelir. Takvimde 🔁 ile haftalık tekrarlanan etkinlik olarak durur.
  Kaldırmak için çift tıkla → **Sil** (bütün tekrarlar silinir).
- **GitHub'a giden:** sadece kod. kayıt klasörü (mail başlıkları, deadline'lar, eklediğin
  siteler/dosyalar) asla gönderilmez.
- **iCloud:** Kayıtlar iCloud'a gitmez; Belgeler klasörün iCloud'da olsa bile kayıt klasörü
  senkronize edilmeyen `~/Library/Application Support` içindedir.

## Dosyalar nerede?

- **Bu klasör** (GitHub'dan indirdiğin): kodun ana kopyası. Burada değişiklik yapıp
  `bash install.sh` çalıştırınca devreye girer.
- **Çalışan program ve kayıtlar:** `~/Library/Application Support/Deadline Hatirlatici/`
  (`app/` kod, `data/` kayıtlar, `venv/` Python). Finder'da **Git → Klasöre Git…** ile açabilirsin.
  Belgeler/Masaüstü iCloud ile senkronize ediliyorsa macOS oradaki dosyaları buluta alıp Mac'ten
  silebiliyor; arka planda çalışan program bu yüzden iCloud dışında durur.

## Ayarlar

`deadline_reminder.py` dosyasının başında:
- `LOOKBACK_DAYS = 120` — kaç günlük mail taransın
- `WINDOW_DAYS = 30` — kaç gün kalanlar gösterilsin
- `MODEL` — kullanılan Claude modeli (Codex'te kendi ayarındaki model kullanılır)

## Kullanım hakkı

Claude ya da ChatGPT hesabın üzerinden çalışır, ayrı ödeme yok. İlk tarama (~800 mail, ~35 istek) kullanım
hakkından bir miktar yer; sonraki taramalar çok küçük. Hakkın çabuk doluyorsa
`MODEL = "sonnet"` yapabilirsin.

## Kaldırma

`bash uninstall.sh` otomatik çalıştırmayı kapatır. Kayıtlar silinmez; tamamen kaldırmak için
`~/Library/Application Support/Deadline Hatirlatici` klasörünü de sil.
