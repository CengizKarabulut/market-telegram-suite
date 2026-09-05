# Market Analysis Engine V3 — Mimari ve Veri Sözleşmesi

Bu belge `market-telegram-suite` için baştan tasarlanan V3 teknik analiz motorunun ilk teknik şartnamesidir.

Amaç mevcut kodu yama ile büyütmek değil; veri, gösterge, piyasa yapısı, Elliott dalga hipotezi, seviye, rejim, kanıt, senaryo, yorum ve sunum katmanlarını birbirinden ayıran deterministik ve test edilebilir bir çekirdek kurmaktır.

## 1. Ana ilkeler

1. Fiyat ve piyasa yapısı merkezde olacaktır; indikatörler kanıt katmanıdır.
2. Hesaplama katmanı yorum metni üretmez.
3. Yorum katmanı yeni seviye veya gösterge hesaplamaz.
4. Gerçekleşmiş bir koşul gelecekteki tetik olarak sunulamaz.
5. Kırılmış seviyelerin rolü değişir; eski destek/direnç otomatik olarak yeniden sınıflandırılır.
6. Elliott Wave tek ve kesin bir sayım üretmez. Birincil ve alternatif hipotezler, geçersizlik seviyeleri ve güven puanı ile birlikte tutulur.
7. Bullish, bearish ve uncertainty kanıtları birbirine karıştırılmaz.
8. Veri kalitesi başarısızsa yorum motoru hard-gate edilir.
9. Tüm sunumlar aynı canonical `MarketState` nesnesini kullanır.
10. Chart bot ve technical bot aynı veri/indikatör/structure çekirdeğini kullanır.

## 2. Katmanlar

### 2.1 Data Engine

Sorumluluklar:
- OHLCV veri alma ve normalizasyon
- benchmark verisi
- seans ve bar durumu
- interval/resample
- corporate action ve veri anomalisi kontrolü
- sağlayıcı ve adjustment metadata

Çıktı: `MarketDataFrame + DataQuality`

### 2.2 Indicator Engine

Sorumluluklar:
- SMA / EMA / WMA
- RSI / MACD / SMI / Stoch RSI / MFI / CCI / Fisher / Momentum
- ADX / DMI
- Bollinger / ATR
- Ichimoku / Supertrend / PSAR
- OBV / CMF / RVOL
- AVWAP / VWAP ailesi

Bu katman yön kararı veya "iyi/kötü" yorumu üretmez.

### 2.3 Structure Engine

Sorumluluklar:
- pivot tespiti
- pivot prominence / ATR mesafesi / zaman ayrımı
- micro / minor / intermediate yapı dereceleri
- HH / HL / LH / LL
- BOS
- CHoCH / yapı karakter değişimi
- kırılmış swing seviyeleri
- reclaim / retest durumu
- structure lifecycle

Bir seviye için en az şu durumlar tutulur:

```text
ACTIVE
TESTED
BROKEN_UP
BROKEN_DOWN
RECLAIMED
REJECTED
STALE
INVALIDATED
```

### 2.4 Elliott Wave Hypothesis Engine

Elliott Wave, Structure Engine'in üzerine kurulan ayrı bir hipotez katmanıdır. Pivotları yeniden icat etmez; teyitli ve derecelendirilmiş pivot dizisini yorumlar.

İlk sürümde desteklenecek yapılar:
- 5 dalgalı impuls adayı: 1-2-3-4-5
- ABC zigzag düzeltme adayı
- ABC flat adayı
- impulse sonrası temel düzeltme ilişkileri

İkinci aşamada:
- triangle
- leading / ending diagonal
- complex W-X-Y

#### Hard rules

Impulsif adaylarda en az:
- Wave 2, Wave 1 başlangıcını geçemez.
- Wave 3, 1-3-5 arasında en kısa dalga olamaz.
- Standart impulse sayımında Wave 4, Wave 1 fiyat alanına giremez.

Diagonal ayrı pattern olarak ele alınır; overlap otomatik hata sayılmaz.

#### Soft evidence

Skorlama unsurları:
- Fibonacci retracement ve extension yakınlığı
- alternation
- dalga süre oranları
- dalga fiyat mesafeleri
- momentum davranışı
- hacim / RVOL davranışı
- Wave 3'te genişleme olasılığı
- Wave 5 momentum divergence olasılığı
- trend/channel uyumu

#### Hipotez modeli

```text
WaveHypothesis
- id
- timeframe
- degree
- pattern_type
- direction
- pivots[]
- active_wave
- confidence
- hard_rule_valid
- soft_score
- invalidation_level
- target_zones[]
- alternate_rank
- reasons[]
- warnings[]
```

Sistem hiçbir zaman yalnızca `Wave 3 içindeyiz` demez. Örnek:

```text
Primary: bearish impulse, active wave = 5, confidence = 0.71
Alternate: ABC correction, active wave = C, confidence = 0.54
```

### 2.5 Level Engine

Tüm seviyeleri tek veri modelinde toplar:
- swing high / low
- BOS / CHoCH seviyeleri
- kırılmış eski destek / direnç
- POC / VAH / VAL
- AVWAP / VWAP
- EMA kümeleri
- previous day / week levels
- Bollinger referansları
- Elliott invalidation seviyeleri
- Elliott Fibonacci target zones
- wave origin / wave termination seviyeleri

Önerilen nesne:

```text
TechnicalLevel
- value
- zone_low
- zone_high
- source
- role
- lifecycle_state
- direction
- distance_pct
- distance_atr
- age_bars
- tests
- broken
- reclaimed
- priority
- actionability
- confidence
- metadata
```

Önemli kural: mevcut fiyatın çok uzağındaki yapısal seviye `near-term trigger` olarak kullanılamaz.

Seviyeler üç sınıfa ayrılır:
- NEAR_TERM
- SECONDARY
- STRUCTURAL

### 2.6 Regime Engine

Durumlar:
- directional trend
- pullback in trend
- range
- squeeze
- expansion
- transition
- failed breakout / breakdown
- high volatility non-directional

Rejim, evidence ağırlıklarını değiştirir ama doğrudan AL/SAT üretmez.

### 2.7 Evidence Engine

Kanıt aileleri:
- structure
- wave
- trend
- momentum
- participation
- relative strength
- location
- volatility
- price action
- multi-timeframe

Her kanıt:

```text
Evidence
- family
- direction: BULLISH | BEARISH | NEUTRAL | UNCERTAINTY
- state
- strength
- confidence
- freshness
- independent_group
- reason
```

`UNCERTAINTY` bearish kanıta eklenmez.

### 2.8 Scenario Engine

Her koşul nesne halinde tutulur:

```text
ScenarioCondition
- id
- side: UP | DOWN | NEUTRAL
- trigger_type
- level / zone
- state: PENDING | TRIGGERED | CONFIRMED | FAILED | INVALIDATED | STALE
- confirmation_rule
- invalidation_rule
- created_at
- source
- priority
```

Ana kural:
- `TRIGGERED`, `CONFIRMED`, `FAILED`, `INVALIDATED` veya `STALE` bir koşul gelecekte yapılması gereken koşul gibi yazılamaz.

### 2.9 Interpretation Engine

Sadece canonical state'i okur.

Yorum sırası:
1. Şu anda ne oluyor?
2. Fiyat nerede?
3. Ana yapı ve Elliott hipotezi ne diyor?
4. En yakın aktif seviyeler hangileri?
5. Momentum/katılım hareketi destekliyor mu?
6. Son barlarda ne değişti?
7. Yukarı senaryo için beklenenler
8. Aşağı senaryo için beklenenler
9. Hangi eski seviyeler kırılmış / rol değiştirmiş?
10. Güven düzeyi ve veri sınırları

### 2.10 Presentation

Canonical state'i kullanan ayrı render katmanları:
- Telegram kısa özet
- Analist kartı
- Teknik harita
- Detay tablo
- PNG
- HTML
- JSON

Presentation katmanı teknik karar üretmez.

## 3. Canonical MarketState

Önerilen üst seviye sözleşme:

```text
MarketState
- symbol
- timestamp
- interval
- price
- change_pct
- bar_state
- data_quality
- indicators
- structure
- wave_hypotheses
- levels
- regime
- evidence
- scenarios
- relative_strength
- multi_timeframe
- changes
- confidence
- limitations
```

## 4. Elliott + Structure birlikte nasıl kullanılacak?

Elliott Wave, HH/HL/LH/LL ve BOS'un yerine geçmez.

Hiyerarşi:

```text
Raw Pivot
  -> Pivot Strength / Degree
  -> Market Structure
  -> BOS / CHoCH / Break Lifecycle
  -> Elliott Candidate Counts
  -> Fibonacci / Wave Target Zones
  -> Level Confluence
  -> Scenario Engine
```

Örnek:
- Swing low 27.98 kırıldı.
- Structure Engine bunu `BROKEN_DOWN` yapar.
- Elliott motoru bu pivotu örneğin Wave 2 sonu veya Wave 4 referansı olarak kullanabilir.
- Level Engine 27.98'i `former_support / reclaim_level / structural` olarak yeniden sınıflandırır.
- Scenario Engine 27.98'i artık `aşağı kırılırsa satış baskısı` koşulu yapamaz.
- Güncel fiyat 21.00 ise yakın aktif seviyeler 21 çevresindeki yapısal ve Elliott/Fibonacci confluence bölgelerinden seçilir.

## 5. ZGYO regression senaryosu

V3 için ilk zorunlu regression testi:

```text
price = 21.00
confirmed_swing_low = 27.98
confirmed_swing_high = 40.50
swing_low_state = BROKEN_DOWN
```

Beklenen davranış:
- 27.98 aşağı yönlü `PENDING` tetik olamaz.
- 27.98 rolü `FORMER_SUPPORT / RECLAIM_LEVEL / STRUCTURAL` olmalıdır.
- genel yorum "27.98 altında kapanırsa satış baskısı güçlenir" diyemez.
- sistem güncel fiyat çevresinde yeni NEAR_TERM support/resistance üretmelidir.
- Elliott hipotezi varsa wave invalidation/target bölgeleri ayrıca gösterilmelidir.

## 6. V3 uygulama sırası

### Faz A — Core foundation
- shared package iskeleti
- canonical modeller
- DataQuality
- interval / provider normalization

### Faz B — Structure V3
- pivot hierarchy
- HH/HL/LH/LL
- BOS / CHoCH
- break lifecycle
- stale / reclaim logic
- ZGYO regression

### Faz C — Elliott V1
- impulse candidate generation
- ABC zigzag / flat
- hard-rule validation
- soft scoring
- primary + alternate counts
- Fib target/invalidation zones

### Faz D — Level V3
- unified level model
- near/secondary/structural classification
- confluence
- stale/broken/reclaim handling

### Faz E — Evidence + Scenario
- four-direction evidence model
- condition state machine
- no-already-triggered-rule invariant

### Faz F — Interpretation
- state-first commentary
- interval-aware language
- wave hypothesis explanation

### Faz G — Presentation
- new analyst card
- technical map
- detail pages
- Telegram integration

### Faz H — Validation
- synthetic unit tests
- historical fixture tests
- symbol regression basket
- walk-forward state-transition tests

## 7. V3 kalite kuralları

Bir release aşağıdakiler sağlanmadan kabul edilmez:
- gerçekleşmiş koşul pending olarak yazılamaz
- kırılmış seviye eski rolüyle kullanılamaz
- Elliott hard rule ihlali primary count olamaz
- primary ve alternate count gerekçeleri JSON'da görünmelidir
- veri kalitesi kritikse commentary kapatılır
- interval yanlış dilde anlatılamaz
- chart ve technical bot aynı canonical hesapları kullanır
- bütün kullanıcı metni canonical state'ten türetilir
