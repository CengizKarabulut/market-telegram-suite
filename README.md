# Market Telegram Suite

Grafik üretimi ile teknik piyasa taramasını tek repoda, iki bağımsız Telegram
botu olarak çalıştıran monorepo.

## Uygulamalar

| Uygulama | Dizin | Telegram komutları |
| --- | --- | --- |
| Grafik botu | apps/chart_bot | /grafik, /kareler, /grafikyardim |
| Teknik analiz botu | apps/technical_bot | /rapor, /tara, /liste, /takip, /esik, /durum |

İki bot aynı Telegram forum grubunda çalışır; her biri yalnız kendi
chat_id + message_thread_id hedefinden gelen komutları işler. Botların
BotFather token'ları farklı olmalıdır. Aynı token ile iki getUpdates
dinleyicisi çalıştırılmamalıdır.

## GitHub Actions secrets

Repository Settings → Secrets and variables → Actions bölümünde:

| Secret | Açıklama |
| --- | --- |
| CHART_BOT_TOKEN | Grafik botunun BotFather token'ı |
| TECHNICAL_BOT_TOKEN | Teknik analiz botunun BotFather token'ı |
| TELEGRAM_CHAT_ID | İki botun bulunduğu forum grubunun -100... kimliği |
| CHART_TOPIC_ID | Grafik botu konu kimliği |
| TECHNICAL_TOPIC_ID | Teknik analiz botu konu kimliği |
| TELEGRAM_ALLOWED_USERS | Teknik botu kullanabilecek Telegram kullanıcı kimlikleri; isteğe bağlı |
| GH_PAT | Bot zincirlerini yeniden başlatmak için actions:write yetkili fine-grained PAT |

GitHub, eski repolardaki secret değerlerini API üzerinden okunabilir biçimde
vermediği için token değerleri yeni repoya manuel olarak eklenmelidir.

## Workflow'lar

- chart-bot.yml: grafik komut botunun uzun bağlantı dinleyicisi
- technical-bot.yml: teknik analiz komut botunun dinleyicisi
- chart-generate.yml: Actions ekranından manuel grafik üretimi
- technical-report.yml: Actions ekranından manuel teknik rapor üretimi
- technical-scan.yml: BIST taraması ve teknik botun /tara hedefi
- ci.yml: iki uygulamanın testleri

Bot workflow'ları farklı token, topic, concurrency grubu, cache ve offset
dosyaları kullanır; birbirlerini durdurmaz veya Telegram güncellemelerini
tüketmez.

## Yerel test

    cd apps/chart_bot
    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v

    cd ../technical_bot
    python -m pip install -r requirements.txt -r requirements-dev.txt
    python -m unittest discover -s tests -v

Uygulamaların ayrıntılı kullanım ve metodoloji belgeleri kendi dizinlerindeki
README dosyalarındadır.

## Geçiş geçmişi

Bu repo aşağıdaki iki kaynak reponun Git geçmişlerini git subtree ile içerir:

- CengizKarabulut/market-chart-lab → apps/chart_bot
- CengizKarabulut/stock-technical-telegram → apps/technical_bot

Eski repolar salt okunur arşiv olarak tutulur; aktif geliştirme bu repoda
devam eder.
