# Stock Technical Telegram

GitHub Actions ekranından bir hisse sembolü girerek görsel teknik durum raporu üretir. PNG ve JSON raporları Actions artifact olarak saklanır; PNG ayrıca Telegram grubundaki belirlenmiş konu başlığına gönderilebilir.

Proje otomatik AL/SAT kararı üretmez. Teknik değerleri ve mevcut durumları raporlar.

## Telegram hedefi

- Grup kimliği: `-1003502567927`
- Konu başlığı: `message_thread_id=1` (General)

Botun gruba eklenmiş ve fotoğraf gönderme yetkisine sahip olması gerekir.

## İlk kurulum

1. Telegram'da `@BotFather` üzerinden bir bot oluşturun.
2. Botu hedef gruba ekleyip mesaj ve fotoğraf gönderme yetkisi verin.
3. GitHub reposunda **Settings → Secrets and variables → Actions** bölümünü açın.
4. `TELEGRAM_BOT_TOKEN` adlı repository secret oluşturup BotFather token'ını değer olarak kaydedin.

Token'ı hiçbir dosyaya, issue'ya veya Actions loguna yazmayın.

## Actions üzerinden çalıştırma

1. **Actions → Hisse Teknik Tarama → Run workflow** yolunu açın.
2. `ticker` alanına `THYAO`, `ASELS`, `TUPRS` veya `AAPL` gibi sembolü girin.
3. BIST sembolleri için `market=BIST` seçin; `.IS` otomatik eklenir.
4. SMA/EMA 377 için günlük grafikte en az `period=2y` kullanın.
5. `send_telegram=true` olduğunda rapor hedef Telegram konusuna gönderilir.

## SMA ve EMA tablosu

Tabloda yalnızca periyot, SMA değeri ve EMA değeri gösterilir:

- Yeşil: fiyat ortalamanın üzerinde
- Sarı: fiyat ortalamaya eşit veya `%0,02` tolerans içinde
- Kırmızı: fiyat ortalamanın altında

Periyotlar:

`5, 8, 10, 13, 20, 21, 34, 50, 55, 89, 100, 144, 200, 233, 377`

## Diğer bölümler

- MACD, Signal ve histogram değişimi
- RSI ve aynı uzunluktaki MA
- Stochastic RSI K/D
- SMI ve EMA3
- MFI ve CCI yumuşatma kesişimleri
- ADX/DMI, Supertrend, VWAP, Ichimoku ve Parabolic SAR
- Bollinger bandwidth percentile, ATR percentile, hacim ve OBV

## Yerel çalıştırma

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.stock_dashboard --ticker THYAO --market BIST --period 2y --interval 1d
```

Telegram gönderimi:

```bash
python -m src.send_telegram
```

Gerekli ortam değişkeni `TELEGRAM_BOT_TOKEN`'dır. Grup ve konu kimlikleri workflow içinde hedef gruba göre ayarlanmıştır.

## Veri ve sorumluluk reddi

Fiyat/hacim verisi `yfinance` üzerinden alınır. Veriler gecikmeli veya eksik olabilir. Rapor yalnızca bilgilendirme ve teknik inceleme amaçlıdır; yatırım tavsiyesi değildir.

