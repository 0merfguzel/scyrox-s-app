# Scyrox S-App

Scyrox V6 / V8 / V6s / V8s kablosuz fareler için **resmi olmayan** bir Windows tepsi uygulaması.
scyrox.net web sürücüsündeki ayarları tarayıcı açmadan değiştirmeyi sağlar.

> Scyrox ile bir bağlantısı yoktur. Protokol, scyrox.net web sürücüsünün davranışı incelenerek çıkarılmıştır.

## Kurulum

[Releases](https://github.com/0merfguzel/scyrox-s-app/releases/latest) sayfasından
`ScyroxSApp-<sürüm>-Setup.exe` dosyasını indirip çalıştırın (Windows 10/11, 64 bit). Uygulama saatin
yanındaki tepsiye yerleşir; ilk açılışta kısa bir tanıtım gösterir.

## Özellikler

- **Otomatik algılama:** Takılı dongle'ı (veya kablolu fareyi) bulur; modeli **ve rengi** fareye sorarak öğrenir.
  Fare uykudayken bile model / renk algılanır. Hem dongle hem kablo takılıysa faresi açık olan seçilir.
  Eski V6'lar rengi yanlış (siyah) bildirebilir; renk Tüm ayarlar → Uygulama ayarları → Fare ikonu rengi ile düzeltilir.
- **Boşta kaynak kullanmaz:** Arka planda zamanlayıcı ya da sorgu yoktur. Fareyle yalnızca tıklayınca,
  menü / pencere açılınca veya bir ayar değişince konuşulur. Takma / çıkarma Windows bildirimiyle algılanır.
- **Pil:** Tepsi ikonuna tek tık → farenin bildirdiği pil yüzdesi (%5'lik adımlar) 10 sn gösterilir.
  Renkler: %0-19 kırmızı, 20-39 turuncu, 40-59 sarı, 60-79 açık yeşil, 80-100 koyu yeşil.
- **Hızlı ayarlar** (sağ tık): polling rate, aktif DPI kademesi, LOD, uyku süresi alt menüleri;
  Motion Sync, angle snapping, ripple control tek tıkla.
- **Tüm ayarlar** (çift tık veya sağ tık → Tüm ayarlar): polling rate, DPI kademeleri ve değerleri, aktif kademe,
  LOD, Motion Sync, angle snapping, ripple control, rekabet modu, 20K FPS, sensör açısı,
  debounce, uyku süresi ve ayrı bir panelde fabrika ayarlarına dönüş. Değişiklikler hemen yazılmaz;
  **Uygula** ile topluca yazılır, **Vazgeç** ile geri alınır. Dil ve fare rengi (yalnızca ikon) gibi
  uygulamaya ait ayarlar pencerenin sol altındaki **Uygulama ayarları** menüsündedir.
- **Dil:** English, Türkçe, Deutsch, Español, Français, Português, Русский, 简体中文, 日本語, 한국어.
  Varsayılan olarak Windows görüntüleme diline göre seçilir (desteklenmiyorsa İngilizce); Tüm ayarlar →
  Uygulama ayarları → Dil ile değiştirilebilir. Yeni dil: `scyrox_sapp/locales/<kod>.py`.
- **İlk açılış:** Kısa bir tanıtım gösterilir. Pil, hızlı ayarlar, tüm ayarlar ve uygulama ayarları
  sayfalarında imlecin nereye tıklanacağını gösterdiği kısa animasyonlar vardır (yalnızca sayfa
  görünürken oynar); görüntüler o anki dil ve temayla çizilir. Kurulumda seçilen dil uygulamanın da dili
  olur. Uygulama ayarları → Tanıtımı göster ile tekrar açılır.
- **Windows açılınca başlat:** Tanıtımın son sayfasında ve Uygulama ayarları menüsünde. Kullanıcının
  `HKCU\…\CurrentVersion\Run` kaydına tek bir `ScyroxSApp` değeri yazar (yönetici izni gerekmez).
  Tik kaldırılınca bu değer silinir; açık olan uygulama kapanmaz, yalnızca bir sonraki oturumda başlamaz.
  Değer hep aynı adla yazıldığından yeni sürüm ya da exe'nin taşınması ikinci bir kayıt oluşturmaz;
  kayıttaki yol açılışta güncellenir. Uygulama tek kopya çalışır (ikinci kez açılırsa hemen kapanır).
- **Güncellemeler:** Açılışta (ve tepsi menüsü açılınca) en fazla günde bir kez GitHub'daki son yayına
  bakılır; uygulamanın internete çıktığı tek yer budur. Uygulama ayarları → Güncellemeleri otomatik
  denetle ile kapatılır, Güncellemeleri denetle ile elle sorulur. Yeni sürüm varsa bildirim gelir ve
  tepsi menüsünde "Güncellemeyi kur" görünür: kurulum dosyası indirilir, sessizce kurulur ve uygulama
  yeniden açılır (Windows yönetici izni sorar). Kurulumsuz (zip) sürümde yalnızca yayın sayfası açılır.
- **Pencere yeri:** Tüm ayarlar, tepsi ikonunun bulunduğu köşede açılır (görev çubuğu üstteyse sağ üst,
  alttaysa sağ alt). Küçük ekranlarda ayarlar kaydırılabilir.
- **Güvenlik:**
  - Yazılan her değer fareden geri okunup doğrulanır.
  - Tanınmayan modellerde ayar yazma kapalıdır.
  - Firmware güncelleme, eşleştirme ve tuş atama bilerek desteklenmez.
  - Beklenmeyen bir hata uygulamayı kapatmaz, `%APPDATA%\ScyroxSApp\error.log` dosyasına yazılır.

## Desteklenen cihazlar

| Model | Renkler | DPI düzeni |
|---|---|---|
| V6 | siyah, beyaz, mavi | 3950 |
| V8 | siyah, beyaz, sarı | 3950 |
| V6s | siyah, beyaz, mavi, pembe | 3955 |
| V8s | siyah, beyaz, sarı | 3955 |

Dongle PID'leri: `F5F4`, `F5F7`, `F517` (Turbo 8K); kablolu: `F5F6`, `F515` (VID `3554`).

## Özel ikonlar

`assets/icons/` klasörüne `<model>_<renk>.ico` veya `.png` koyun (örn. `V8_yellow.png`).
Renk anahtarları: `black`, `white`, `blue`, `yellow`, `pink`, `red`.
Arama sırası: `V6s_white` → `V6_white` (aynı kasa) → herhangi bir `*_white`.
Hiçbiri yoksa farenin rengine boyanmış basit bir ikon çizilir.

Hazır ikonlar (fare ikonları, exe'nin beş fareli ikonu `packaging/icons/ScyroxSApp.ico` ve
kurulumun dongle ikonu `packaging/icons/V6_white_dongle.ico`) Scyrox ürün fotoğraflarından bir kez
üretildi. Fotoğraflar ve üretim aracı telif nedeniyle repoda yoktur.

## Kaynaktan çalıştırma

Python 3.10 veya üstü gerekir.

```bash
pip install -r requirements.txt
```

```bash
python -m scyrox_sapp
```

Ya da `ScyroxSApp.pyw` dosyasına çift tıklayın (konsol penceresi açılmaz).

## Yayın sürümü (exe ve kurulum)

```bash
pip install pyinstaller
```

```bash
winget install JRSoftware.InnoSetup
```

```bash
python packaging/build.py
```

Çıktılar (Masaüstü'ne; başka hedef için `python packaging/build.py D:\Yayın`):

- `ScyroxSApp-<sürüm>-Setup.exe` (~21 MB): kurulum. `C:\Program Files\Scyrox S-App` klasörüne
  kurar (yönetici izni ister), Başlat menüsüne kısayol ekler.
  Yeni sürüm eskisinin üstüne kurulur (çalışan uygulamayı kapatıp yeniden açar). Kaldırınca başlangıç
  kaydı ve `%APPDATA%\ScyroxSApp` ayarları da silinir.
- `ScyroxSApp\ScyroxSApp.exe` (+ `_internal`, ~70 MB) ve zip'i `ScyroxSApp-<sürüm>-portable.zip`:
  kurulumsuz sürüm; klasör bütün olarak taşınır. Boyutun çoğu Qt ve Python çalışma zamanıdır.

Yeni sürüm yayınlamak: `scyrox_sapp/__init__.py` içindeki `__version__` artırılır, derlenir,
GitHub'da `v<sürüm>` etiketiyle bir release açılıp `…-Setup.exe` ve `…-portable.zip` eklenir. Kurulu uygulamalar
bunu bir gün içinde görür.

## Testler

```bash
python -m unittest discover -s tests -t .
```

## Lisans

MIT, bkz. [LICENSE](LICENSE). Scyrox adı ve ürün görselleri sahiplerine aittir.
