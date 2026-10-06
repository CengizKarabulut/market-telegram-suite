# X → Telegram Relay

Korumalı (private/protected) X hesabındaki yeni gönderileri resmi X API ile okuyup
Telegram'a aktaran bağımsız uygulama.

## Davranış

- X hesabı herkese açılmaz.
- OAuth 1.0a **User Context** kullanılır.
- Varsayılan olarak reply ve repostlar aktarılmaz; quote postlar aktarılır.
- Fotoğraf, video ve animated GIF ekleri Telegram'a taşınır.
- Uzun gönderilerde `note_tweet.text` tercih edilir.
- Telegram mesajlarında `protect_content=true` varsayılandır.
- İlk çalıştırmada eski gönderiler topluca gönderilmez; en yeni gönderi başlangıç
  noktası olarak kaydedilir.
- Son görülen X gönderi kimliği GitHub Actions cache içinde tutulur; aynı gönderi
  tekrar gönderilmez.
- Zamanlar Europe/Istanbul saat diliminde gösterilir.

## X Developer ayarı

X Developer Console'da kendi hesabın için bir Project/App oluştur:

1. App izinlerini en az **Read** olarak ayarla.
2. User authentication içinde OAuth 1.0a erişimini etkinleştir.
3. Consumer Keys bölümünden API Key ve API Key Secret değerlerini al.
4. Korumalı X hesabına bağlı Access Token ve Access Token Secret üret.
5. Tokenları repoya yazma; yalnız GitHub Actions Secrets olarak sakla.

Gerekli X secret'ları:

- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

## Telegram ayarı

BotFather'dan bir bot oluştur veya yalnız gönderim için mevcut bir bot tokenını
kullan. Bot hedef kanal/grupta mesaj gönderebilmelidir.

Gerekli Telegram secret'ları:

- `X_RELAY_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `X_RELAY_TOPIC_ID` — forum konusu kullanılıyorsa; aksi halde boş bırakılabilir.

## Çalıştırma

Workflow: `.github/workflows/x-relay.yml`

Workflow dosyası her 5 dakikada bir tetiklenir ancak `X_RELAY_ENABLED` repository variable değeri `true` olmadan relay job'u çalışmaz. Secrets tamamlandıktan sonra bu variable'ı `true` yap. Ayrıca Actions ekranından manuel tetikleme yapılabilir.

Yerelde:

```bash
cd apps/x_relay_bot
python -m pip install -r requirements.txt
export X_API_KEY="..."
export X_API_SECRET="..."
export X_ACCESS_TOKEN="..."
export X_ACCESS_TOKEN_SECRET="..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python src/x_relay.py
```

## GitHub Actions variable

Repository **Settings → Secrets and variables → Actions → Variables** bölümünde:

- `X_RELAY_ENABLED=true` — yalnız tüm secret'lar girildikten sonra etkinleştir.

## İsteğe bağlı ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
| --- | --- | --- |
| `TELEGRAM_TOPIC_ID` | boş | Telegram forum topic ID |
| `X_EXCLUDE_REPLIES` | `true` | Reply gönderilerini atla |
| `X_EXCLUDE_RETWEETS` | `true` | Repostları atla |
| `TELEGRAM_PROTECT_CONTENT` | `true` | Telegram iletme/kaydetme korumasını iste |
| `X_RELAY_BOOTSTRAP_SEND_LATEST` | `false` | İlk çalıştırmada yalnız en son mevcut postu da gönder |
| `X_RELAY_STATE_PATH` | `state/last_seen.json` | Tekrar önleme state dosyası |

## Güvenlik

API anahtarlarını, X tokenlarını veya Telegram bot tokenını hiçbir zaman kaynak
koda, issue'ya veya loglara yapıştırma. GitHub Secrets kullan.
