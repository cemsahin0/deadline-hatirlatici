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
| **Çift tık** | deadline'ın geldiği maili Mail'de (ya da ders sitesini tarayıcıda) açar |
| **Sürükle** | notu istediğin yere taşı (yeri hatırlanır) |
| **◢ (sağ alt köşe)** | sürükleyerek boyutunu ayarla (boyut hatırlanır) |
| **–** | notu tek satıra küçültür ("4 deadline · 1 acil!") |
| **⟳** | mailleri hemen tarar (normalde açılışta ve her 10 dakikada bir) |
| **Sağ tık** | menü: şimdi tara, ders sitesi ekle/düzenle, bitti işaretlenenleri geri getir, kapat |

## Ders siteleri

Bazı hocalar duyuruları mail yerine kendi sitesine koyuyor. Post-it'e **sağ tık → Ders sitesi ekle…**
deyip sayfanın linkini yapıştır; deadline'lar maillerdekiyle aynı şekilde listeye eklenir.
Listeyi **sağ tık → Ders sitelerini düzenle** ile açıp link silebilirsin (`data/sites.txt`).

Siteye zarar vermemek için:
- Her site en fazla **6 saatte bir**, tek bir sayfa isteğiyle okunur (günde ~4 istek; linkler takip edilmez).
- Sayfa değişmediyse sunucu içeriği tekrar göndermez (ETag / Last-Modified), Claude'a da sorulmaz.
- Site `robots.txt` ile bu tür araçları engelliyorsa okunmaz.

Not: Sadece giriş gerektirmeyen, normal web sayfaları okunabilir (SUCourse gibi şifreli sayfalar
ve PDF dosyaları okunamaz).

Hocanın sonradan uzattığı/değiştirdiği tarihler otomatik güncellenir: mailler eskiden yeniye
okunur, en son duyurulan tarih geçerli olur, iptal edilenler listeden düşer. Her taramanın
sonunda aynı işin tekrar eden kayıtları da ayıklanır.

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
