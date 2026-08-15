# Stock Technical Telegram

GitHub Actions ekranından bir hisse sembolü girerek kapsamlı teknik piyasa durum raporu üretir. PNG ve JSON raporları Actions artifact olarak saklanır; PNG ayrıca Telegram grubunun Genel konusuna gönderilir.

Sistem otomatik AL/SAT kararı veya birleşik puan üretmez. Rejim, yapı, konum, trend, momentum, katılım ve volatilite durumlarını tarafsız biçimde raporlar.

İki ürün bilinçli olarak farklı kapsam taşır:

- **Pine:** TradingView üzerinde gerçek zamanlı teknik teşhis panelidir.
- **Python/Telegram:** CANLI/TEYİTLİ ayrımı yapan market-context raporu ve kapanış sonrası watchlist durum tarayıcısıdır.

Ana kullanım swing/pozisyon araştırması ve kapanış sonrası izlemedir. Kimlik doğrulamasız gecikmeli veri nedeniyle intraday/scalping karar sistemi değildir.

## Telegram hedefi

- Grup kimliği: `-1003502567927`
- Konu: Genel
- Genel konuya gönderimde `message_thread_id` boş bırakılır.

Telegram bağlantısındaki `_1` değeri Bot API konu kimliği değildir. `message_thread_id=1` kullanılması `message thread not found` hatasına neden olur.

## İlk kurulum

1. Telegram'da `@BotFather` üzerinden bir bot oluşturun.
2. Botu hedef gruba ekleyip mesaj ve fotoğraf gönderme yetkisi verin.
3. GitHub reposunda **Settings → Secrets and variables → Actions** bölümünü açın.
4. `TELEGRAM_BOT_TOKEN` adlı repository secret oluşturup BotFather token'ını kaydedin.

Token'ı hiçbir dosyaya, issue'ya veya Actions loguna yazmayın.

## Actions üzerinden çalıştırma

1. **Actions → Hisse Teknik Tarama → Run workflow** yolunu açın.
2. `ticker` alanına `THYAO`, `ASELS`, `TUPRS` veya `AAPL` gibi sembolü girin.
3. BIST hisselerinde `market=BIST`, `provider=AUTO` seçilmesi önerilir.
4. İstenirse `anchor_date` alanına manuel AVWAP başlangıcı `YYYY-MM-DD` biçiminde yazılır. Tarih indirilen mum aralığında olmalıdır; boşsa yıl başlangıcı kullanılır.
5. `period=6mo` veya `1y` seçilebilir; sistem 377 bar göstergeler için arka planda en az `warmup_period=2y` indirir. İstenen dönem ile gösterge warm-up dönemi ayrıdır.
6. `benchmark` boşsa BIST için `XU100`, ABD için `SPY` kullanılır.
7. `account_size=0` risk bütçesi/adet hesabını kapatır; ATR mesafe referansı yine gösterilir.
8. `send_telegram=true` olduğunda rapor Telegram grubunun Genel konusuna gönderilir.

Sağlayıcı seçenekleri:

- `AUTO`: BIST için önce borsapy/TradingView; hata halinde yfinance yedeği.
- `BORSAPY`: BIST için TradingView WebSocket verisini zorunlu kullanır.
- `YFINANCE`: yfinance kaynağını zorunlu kullanır.

## Piyasa durum haritası

Raporun üst özeti puan vermeden şu aileleri gösterir:

- Rejim: yönlü/genişleyen, yönlü/kontrollü, dengeli/sıkışan, yüksek volatilite/yönsüz veya geçiş/karma.
- Yapı: teyitli pivotlardan HH/HL/LH/LL ve son BOS olayı.
- Konum: Value Area, POC, AVWAP, önceki gün ve önceki hafta seviyeleri.
- Trend: fiyatın kaç EMA üzerinde olduğu, yükselen EMA sayısı ve EMA yayılımı.
- Momentum: MACD, RSI, Stochastic RSI ve SMI çizgi ilişkilerinin uyumu.
- Katılım: hacim, RVOL, OBV ve açıkça etiketlenmiş OHLCV delta/CVD tahmini.
- Volatilite: ATR percentile ile Bollinger bandwidth percentile ve genişleme/daralma.

## Karar bağlamı

- **Bar durumu:** BIST düzenli seansında güncel günlük mum `CANLI`; kapanmış mumlar ve geçmiş olaylar `TEYİTLİ` gösterilir. Tatil/yarım gün takvimi henüz yoktur; kullanılan seans varsayımı JSON'da yer alır.
- **Relative Strength:** hisse/XU100 oranı, 1/5/20/60/252 bar göreceli getiri farkları ve oran eğimi. Temettü toplam getirisi değildir.
- **MTF confluence:** günlük veriden oluşturulan günlük, haftalık ve aylık eğilim bağlamı. Canlı son günlük mum MTF hesabından çıkarılır.
- **Likidite:** kapanış × lot hacmiyle 20 günlük ortalama TL işlem hacmi, son 60 günlük medyan ve borsapy'den alınabilirse halka açıklık yüzdesi. Manipülasyon tespiti değildir.
- **Risk referansı:** mevcut kapanıştan mekanik ATR mesafesi ve isteğe bağlı risk bütçesi/adet senaryosu. Destek/direnç veya emir önerisi değildir.

## Eşik metodolojisi

Eşikler şimdilik sezgiseldir; istatistiksel olarak kalibre edilmiş bir tahmin modeli veya backtest edilmiş AL/SAT sistemi değildir.

| Alan | Eşik |
| --- | --- |
| Yönlü rejim | ADX ≥ 25 |
| Denge adayı | ADX < 20 |
| Genişleme | ATR veya BB percentile ≥ 60 |
| Sıkışma | BB percentile ≤ 25 ve MA spread percentile ≤ 30 |
| Yüksek yönsüz volatilite | ADX < 20 ve BB percentile ≥ 70 |
| BIST düşük TL likiditesi | Ort.20 < 25 milyon TL |
| BIST yüksek TL likiditesi | Ort.20 ≥ 100 milyon TL |
| Düşük halka açıklık uyarısı | <%10 |

Rejim değişimi iki ardışık aday barla kalıcı hâle gelir. ADX eğimi ve MA spread yönü `trend oluşuyor / genişliyor / yavaşlıyor` ayrımında kullanılır. Bu eşiklerin gelecekteki doğrulaması ayrı, önceden tanımlanmış walk-forward/event-study modülünde yapılmalıdır.

## SMA ve EMA

Tabloda her periyodun kendi SMA ve EMA değeri bulunur:

`5, 8, 10, 13, 20, 21, 34, 50, 55, 89, 100, 144, 200, 233, 377`

- Yeşil: fiyat ortalamanın üzerinde.
- Sarı: fiyat ortalamaya eşit veya `%0,02` tolerans içinde.
- Kırmızı: fiyat ortalamanın altında.

## Momentum ayrıntıları

- MACD level, signal, sıfır çizgisi ve histogramın dört durumlu yorumu.
- RSI ve aynı uzunlukta MA14.
- Stochastic RSI K/D; normal Stochastic özellikle dahil edilmez.
- Kullanıcının verdiği çift EMA yumuşatmalı SMI ve EMA3 sinyali.
- MFI/MA14 ve CCI/MA20.
- Yukarı/aşağı kesişimler, normalize fark ile “kesişime yakın” ayrımı.
- Her ana osilatör için 1 bar değişim, 3 bar değişim ve 5 bar doğrusal eğim.
- RSI, MACD ana çizgisi ve SMI için TradingView RSI örneğiyle aynı 5 sol/5 sağ teyitli osilatör pivotları kullanılır. Pivotlar arası mesafe 5–60 bardır.
- Normal pozitif: fiyat LL/osilatör HL; normal negatif: fiyat HH/osilatör LH. Gizli pozitif: fiyat HL/osilatör LL; gizli negatif: fiyat LH/osilatör HH.
- Pivot mesafesi ile güncellik ayrıdır: yalnız son 5 barda teyit edilen uyumsuzluklar aktif olarak momentum tablosu, olaylar, JSON ve Telegram'da gösterilir. Sağdaki 5 bar tamamlanmadan pivot teyitli kabul edilmez; uyumsuzluk tek başına AL/SAT sinyali değildir.

## Trend, volatilite ve katılım

- ADX/DMI ve ADX tarihsel percentile.
- Supertrend, Ichimoku ve Parabolic SAR.
- Bollinger alt/orta/üst bant konumu, bant genişliği ve percentile.
- ATR, ATR%, ATR percentile ve çok barlı eğim.
- Hacim/SMA20, hacim percentile ve RVOL.
- OBV, OBV EMA20 ve eğim.

## Konum ve hacim profili

- Manuel AVWAP; tarih girilmezse yıl başı anchor.
- Ay, çeyrek ve yıl VWAP değerleri.
- PDH, PDL, PDC; PWH, PWL, PWC ve mevcut hafta açılışı.
- Son 100 bar için yaklaşık POC, VAH, VAL ve `%70` Value Area.
- POC uzaklığı yüzde ve ATR cinsinden.
- Bin genişliği ve ATR eşiğini birlikte kullanan developing POC göçü.
- Mevcut profile göre acceptance ile her bardaki rolling VAH/VAL'a göre developing acceptance ayrı gösterilir.
- Grafikte bugünkü seviyeyi geçmişe uzatan sabit çizgiler yerine rolling POC/VAH/VAL gösterilir.
- Son teyitli MACD, RSI, Stochastic RSI, SMI, Bollinger, Supertrend, BOS ve profil seviye olayları.

### Önemli veri sınırı

GitHub raporu TradingView'dan OHLCV mumlarını alır; TradingView Premium `request.footprint()` verisine erişmez. Bu nedenle:

- POC/VAH/VAL, mum hacminin barın fiyat aralığına dağıtılmasıyla hesaplanan yaklaşık profildir.
- Buy volume, sell volume, delta ve CVD değerleri kapanışın bar aralığındaki konumuna dayanan `OHLCV proxy` olarak açıkça etiketlenir.
- Bu değerler gerçek footprint/order-flow verisi gibi yorumlanmamalıdır.

Gerçek footprint imbalance ve gerçek buy/sell delta ayrı bir TradingView Premium Pine modülü gerektirir. Günlük workflow'da Opening Range kullanılmadığı için rapora eklenmemiştir; intraday aralık desteği açıldığında OR15/OR30/OR60 ayrı modül olarak eklenebilir.

Lower-timeframe (30m/60m) profil, günlük OHLCV yaklaşımını iyileştirecek ayrı bir P1 veri modülüdür; mevcut sürüm bunu kullanıyormuş gibi davranmaz.

## Zamanlanmış watchlist taraması

`watchlist.txt` dosyasına her satırda bir BIST sembolü yazılır. **Zamanlanmış Watchlist Taraması** workflow'u hafta içi `16:30 UTC / 19:30 Türkiye` saatinde çalışır. Varsayılan durum koşulu Bollinger genişlik percentile ≤ 20 ve RVOL ≥ 1,5'tir. Yalnız eşleşme varsa Telegram metni gönderilir; bu bir AL/SAT sinyali değildir.

Yerel kullanım:

```bash
python -m src.watchlist_scan --watchlist watchlist.txt --period 2y --provider AUTO
```

## Yerel çalıştırma

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.stock_dashboard --ticker THYAO --market AUTO --provider AUTO --period 6mo --warmup-period 2y --interval 1d --benchmark XU100 --anchor-date 2026-01-02
```

Telegram gönderimi:

```bash
python -m src.send_telegram
```

`TELEGRAM_MESSAGE_THREAD_ID` boş olduğunda Genel konu kullanılır. Başka bir forum konusu için Bot API'den alınan gerçek konu kimliği verilebilir.

## Veri ve sorumluluk reddi

BIST verisi varsayılan olarak [borsapy](https://github.com/saidsurucu/borsapy) aracılığıyla TradingView WebSocket kaynağından alınır. Kimlik doğrulamasız TradingView verisi yaklaşık 15 dakika gecikmelidir. JSON çıktısındaki `data_provider`, `resolved_market`, `bar_state`, `download_period` ve `price_adjustment` alanları o çalışmada fiilen kullanılan veri bağlamını gösterir.

borsapy/TradingView yolu split-adjusted sağlayıcı varsayımını kullanır, temettü toplam getirisi değildir. yfinance yolu `auto_adjust=False` kullanır ve `Adj Close` teknik hesaplara uygulanmaz. KAP haberleri ve temel veri mevcut teknik durum motoruna dahil değildir; bunlar ayrı kaynak zamanı ve doğrulama gerektirir.

borsapy kişisel ve eğitim amaçlı kullanım için sunulmaktadır; ticari kullanımda ilgili piyasa veri lisansları gerekir. Veriler gecikmeli veya eksik olabilir. Rapor yalnızca bilgilendirme ve teknik inceleme amaçlıdır; yatırım tavsiyesi değildir.
