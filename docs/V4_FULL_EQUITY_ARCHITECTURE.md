# V4 Full Equity Analysis Engine

## Amaç

V4, V3 teknik çekirdeğini kaldırmaz. V3/V4 teknik durum motorunu bir alt sistem olarak kullanır ve bunun yanına **point-in-time finansal veri, temel kalite, günlük değerleme, kurumsal olay ve deterministik analist sentezi** ekler.

Nihai amaç tek bir `AL/SAT` skoru üretmek değildir. Sistem birbirinden ayrı eksenlerde neyin güçlü, neyin zayıf ve neyin belirsiz olduğunu açıklamalıdır:

- Teknik yapı
- Teknik değişim / son barda ne değişti
- Temel finansal kalite
- Büyüme ve kârlılık
- Bilanço / finansal risk
- Değerleme
- Kurumsal olaylar
- Katalizörler ve riskler
- Kanıt netliği

## Ana ilke: Point-in-time

Finansal tablo yalnız piyasaya açıklandığı andan itibaren kullanılabilir.

Örnek:

- Dönem sonu: 2026-06-30
- KAP yayımlanma zamanı: 2026-08-10 18:24

Bu tablo 2026-08-10 18:24 öncesindeki hiçbir tarihsel analizde veya backtestte kullanılamaz. Dönem sonu tek başına veri erişim tarihi değildir.

Her finansal snapshot en az şu alanları taşır:

```text
FinancialSnapshot
- symbol
- sector_type
- period_end
- published_at
- statement_type
- currency
- scale
- audit_status
- inflation_accounting
- restatement_id
- source
- income_statement
- balance_sheet
- cash_flow
- shares_outstanding
- metadata
```

## Canonical üst model

```text
EquityAnalysisState
 ├── market_state
 │    ├── technical_features
 │    ├── technical_changes
 │    ├── structure
 │    ├── levels
 │    ├── elliott
 │    ├── relative_strength
 │    ├── multi_timeframe
 │    └── scenarios
 ├── fundamental_state
 │    ├── latest_available_snapshot
 │    ├── ttm
 │    ├── growth
 │    ├── profitability
 │    ├── leverage
 │    ├── cash_quality
 │    └── sector_metrics
 ├── valuation_state
 │    ├── market_cap
 │    ├── enterprise_value
 │    ├── multiples
 │    ├── historical_percentiles
 │    ├── peer_percentiles
 │    ├── model_ranges
 │    └── valuation_band
 ├── corporate_events
 ├── risks
 ├── catalysts
 ├── evidence
 └── analyst_interpretation
```

## Katmanlar

### 1. Fundamental Data Engine

Görevi ham finansal veriyi almak, fakat yorumlamamak.

Sorumluluklar:

- Finansal tablo dönem sonu ve yayımlanma zamanını ayrı saklamak
- Para birimi ve ölçek bilgisini korumak
- Denetim durumunu korumak
- Yeniden düzenlenmiş tabloları tanımlamak
- TMS 29 / enflasyon muhasebesi metadata'sını saklamak
- Pay sayısını tarihsel geçerlilik tarihiyle saklamak
- Kaynak ve veri kalitesi bilgisini taşımak

Veri sağlayıcısı uygulama içine gömülmemeli. Provider adapter sözleşmesi kullanılmalı.

### 2. Point-in-Time Snapshot Resolver

Bir `as_of` zamanı için yalnız o anda gerçekten bilinebilen snapshot'ı seçer.

Hard invariant:

```text
snapshot.published_at <= as_of
```

Sonradan yayımlanan veya yeniden düzenlenen finansallar geçmiş tarihe sızamaz.

### 3. TTM Assembly Engine

Türk şirketlerinde ara dönem tabloları çoğunlukla yılbaşından itibaren kümülatiftir. Bu nedenle TTM, çeyrek değerleri kör biçimde toplamaz.

Motor:

- kümülatif gelir tablosu kalemlerini gerektiğinde dönem farkına çevirir,
- yıllık + cari ara dönem - geçen yıl aynı ara dönem mantığını destekler,
- yeniden düzenlenmiş ve farklı muhasebe bazlı dönemleri karıştırmaz,
- eksik dönemlerde `unavailable` döndürür; tahmin uydurmaz.

### 4. Fundamental Metrics Engine

Genel sanayi şirketleri için başlangıç ailesi:

- Satış büyümesi
- Brüt kâr marjı
- FAVÖK marjı
- Net kâr marjı
- ROE
- ROA
- ROIC
- Net borç / FAVÖK
- Faiz karşılama
- İşletme sermayesi değişimi
- Operasyonel nakit akışı / net kâr
- Serbest nakit akışı
- Nakit dönüşüm kalitesi

Negatif veya anlamsız paydalarda oran `ucuz/pahalı` olarak yorumlanmaz; `not_meaningful` veya `unavailable` olur.

### 5. Daily Valuation Engine

Finansal snapshot, yeni tablo gelene kadar sabit kalabilir; değerleme ise fiyat değiştikçe günlük yeniden hesaplanır.

Temel formüller:

```text
market_cap = current_price × valid_shares_outstanding
enterprise_value = market_cap + net_debt
P/E = market_cap / TTM net_income
P/B = market_cap / equity
P/S = market_cap / TTM revenue
EV/EBITDA = enterprise_value / TTM EBITDA
FCF Yield = TTM free_cash_flow / market_cap
```

Kurallar:

- Net kâr <= 0 ise P/E `not_meaningful`.
- Özsermaye <= 0 ise P/B yorumlanmaz.
- Pay sayısı bilinmiyorsa market cap ve ona bağlı oranlar üretilmez.
- Para birimi / ölçek uyumsuzluğu hard-gate sebebidir.

### 6. Historical & Peer Valuation Engine

Sabit `F/K < 10 ucuzdur` benzeri eşikler ana yöntem değildir.

Tercih edilen karşılaştırmalar:

- Şirketin kendi 3-5 yıllık dağılımı
- Sektör medyanı
- Benzer şirket grubu
- Büyüme, ROE ve borç kalitesine göre bağlam

Çıktı örnekleri:

```text
P/E historical_percentile: 22
P/B sector_percentile: 34
EV/EBITDA historical_state: BELOW_NORMAL_BAND
valuation_context: DISCOUNTED_VS_HISTORY_BUT_WEAKER_ROE
```

### 7. Sector Profile Engine

Aynı değerleme modeli her şirkete uygulanmaz.

#### Sanayi / hizmet

- P/E
- EV/EBITDA
- FCF yield
- ROIC
- borçluluk
- marjlar
- DCF yalnız gerekli veri kalitesi varsa

#### GYO

ZGYO pilotu için özel profil zorunludur.

- Portföy / ekspertiz değeri
- Güvenilir NAV varsa NAV ve NAV iskontosu
- Özkaynak
- Net borç
- LTV
- Kira / operasyonel gelir
- Tekrarlayan nakit üretimi
- Gerçeğe uygun değer artışlarının net kârdan ayrıştırılması

**Özkaynak NAV değildir.** Güvenilir portföy/NAV verisi yoksa sistem NAV iskontosu uydurmaz.

#### Banka

- P/B
- ROE
- sermaye yeterliliği
- aktif kalitesi
- net faiz marjı
- takipteki kredi göstergeleri

#### Holding

- iştirak NAV
- solo net nakit/borç
- holding iskontosu

### 8. Valuation Model Engine

Tek fiyat hedefi yerine bant üretir.

```text
ValuationBand
- lower
- central
- upper
- methods
- confidence
- assumptions
- limitations
```

Sektöre göre yöntemler:

- Sanayi: tarihsel/peer multiples + gerektiğinde DCF
- GYO: NAV tabanlı bant + peer P/B/NAV bağlamı
- Banka: P/B–ROE ilişkisi
- Holding: NAV iskonto bandı

### 9. Corporate Event Engine

KAP olayları doğrudan fiyat tahminine çevrilmez. Yapılandırılmış kanıt üretir.

Başlangıç olay aileleri:

- Sermaye artırımı / azaltımı
- Temettü
- Geri alım
- Ortak / yönetici pay işlemleri
- Yeni sözleşme
- Yatırım / kapasite artışı
- Finansman / kredi
- Dava / düzenleyici risk
- Varlık alım-satımı
- Ortaklık yapısı değişimi

Her olay:

```text
CorporateEventEvidence
- event_type
- published_at
- direction
- strength
- confidence
- materiality
- reason
- source
```

### 10. Analyst Synthesis Engine

Bu katman yeni finansal veya teknik hesap yapmaz. Canonical state içindeki kanıtları önem sırasına koyar ve açıklama üretir.

Sıralama:

1. Veri kalitesi / as-of
2. Teknik yapı ve son değişimler
3. Temel kalite
4. Borç / nakit riski
5. Değerleme bağlamı
6. Kurumsal olaylar
7. Katalizörler
8. Çelişkiler
9. Senaryolar
10. Sınırlamalar

Örnek deterministik çıktı mantığı:

```text
Ana görünüm:
Şirketin operasyonel kârlılığı son iki açıklanan dönemde iyileşirken borçluluk da geriliyor.
Buna karşılık fiyat teknik olarak son teyitli yapının altında ve momentum zayıf.
Mevcut değerleme şirketin tarihsel bandının alt tarafında olsa da bu iskonto daha düşük ROE ile birlikte okunmalı.
Bu nedenle temel taraftaki iyileşme henüz teknik trend dönüşü ile teyit edilmiş değil.
```

Her cümle bir hesaplanmış field veya evidence nesnesine bağlanabilir olmalıdır.

## Veri kalitesi ve hard gates

Aşağıdaki durumlar ilgili hesap ailesini durdurur:

- Gelecek tarihli finansal snapshot
- Bilinmeyen yayımlanma zamanı
- Para birimi/ölçek uyuşmazlığı
- Geçersiz pay sayısı
- Uyumlu olmayan restatement bazları
- TMS 29 öncesi/sonrası uyumsuz toplama
- Eksik TTM bileşenleri
- Negatif paydadan anlamsız valuation yorumu
- Güvenilir NAV olmadığı halde NAV iskontosu üretme girişimi

Hard-gate tüm raporu zorunlu olarak susturmaz; hangi aile bozuksa yalnız o aile `unavailable` olur. Kritik fiyat veri kalitesi ise mevcut V3 davranışı gibi teknik yön/seviye yorumunu durdurabilir.

## Test matrisi

Zorunlu testler:

- `published_at > as_of` olan finansal tablo görünmez
- yayımlanma anında snapshot erişilebilir hale gelir
- geçmiş analiz daha yeni restatement kullanmaz
- negatif net kârda P/E anlamlı değer üretmez
- sıfır/negatif özsermayede P/B yorumu üretmez
- eksik pay sayısında market cap fail-closed olur
- fiyat değişirken aynı snapshot ile valuation multiple değişir
- kümülatif ara dönem TTM doğru normalize edilir
- para birimi ve ölçek uyuşmazlığı engellenir
- TMS 29 uyumsuz dönemler kör şekilde toplanmaz
- GYO'da özkaynak NAV yerine kullanılmaz
- sektör profili yanlış metrik ailesini çalıştırmaz
- deterministik analyst synthesis aynı input için aynı output verir
- hiçbir cümle source/evidence olmadan üretilemez

## Uygulama sırası

### Faz A — mevcut teknik çekirdeği sabitle

- Technical Feature Engine
- Technical Change Engine
- scanner/MA adapter contract
- conflict-aware synthesis
- gerçek ZGYO preview

### Faz B — temel veri sözleşmesi

- `fundamental_models.py`
- point-in-time resolver
- scale/currency/restatement validation
- test fixtures

### Faz C — metrik motoru

- TTM assembly
- generic industrial metrics
- GYO sector profile

### Faz D — günlük değerleme

- shares-as-of
- market cap / EV
- multiples
- historical percentile contract

### Faz E — tam sentez

- EquityAnalysisState
- risk/catalyst evidence
- sector valuation band
- final Telegram/report/card presentation

### Faz F — production geçişi

V4 yeterli regresyon ve gerçek veri testi tamamlanmadan mevcut `/rapor` davranışı değiştirilmez. Yeni motor önce opt-in preview/komut olarak kalır.
