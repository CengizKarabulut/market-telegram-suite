# V4 Full Equity Analysis — Scanner + MA Level Integration

Bu belge `market-telegram-suite` icin hedeflenen tam hisse analizinin tarama ve dinamik destek/direnc katmanlarini tanimlar.

## Ana ilke

Sistem hicbir tekil tarama sinyalini, indikatörü, hareketli ortalamayi veya temel orani nihai karar olarak kullanmaz. Her kaynak kendi kanit ailesini üretir; sentez katmani uyumu, celiskiyi, zaman dilimini, tazeligi ve veri kalitesini acikca raporlar.

`Taramabot` ve `ma-reaction-scanner` gelismeye devam edebilecegi icin `market-telegram-suite` bu repolarin ic implementasyonuna baglanmaz. Aradaki baglanti versioned contract/adapter ile kurulur.

## 1. Scanner Evidence — taramabot

Amaç: Bir hisse raporu istendiginde taramabot icinde o hisse icin hangi taramalarin/sinyallerin uydugunu, hangi zaman diliminde olustugunu ve hala gecerli olup olmadigini rapora eklemek.

Onerilen contract:

```text
ScanSignal
- source = taramabot
- source_version
- scanner_code
- scanner_name
- symbol
- timeframe
- side: BUY | SELL | NEUTRAL
- state: NEW | ACTIVE | CONFIRMED | WEAKENING | INVALIDATED | EXPIRED
- triggered_at
- age_bars
- trigger_price
- conditions_met[]
- conditions_failed[]
- invalidation_level
- exit_condition
- strength
- confidence
- data_quality
```

Rapor dili sinyal kelimesini baglamdan koparmaz. Ornek:

```text
Taramabot: S-M-V-1 / 4s · AL adayi · 2 bar once
Teknik yapi uyumu: Kismi
Aciklama: SMI/MACD ve hacim kosullari uyuyor; ancak ana swing yapisinda yukari BOS henuz yok.
```

## 2. MA Level Evidence — ma-reaction-scanner

Amaç: Fiyatin gercekte saygi duydugu hareketli ortalamalari zaman dilimine gore dinamik destek/direnc olarak kullanmak.

Bu katman klasik swing/volume-profile seviyelerinin yerine gecmez. `Level Engine` icinde ayri bir kaynak ailesidir.

Onerilen contract:

```text
MALevelEvidence
- source = ma-reaction-scanner
- source_version
- symbol
- timeframe
- ma_type
- ma_period
- ma_value
- side: SUPPORT | RESISTANCE
- distance_pct
- distance_atr
- level_score
- level_class
- level_touches
- hold_rate_pct
- median_bounce_atr
- reaction_1atr_rate_pct
- reaction_2atr_rate_pct
- median_penetration_atr
- cross_per_100
- plateau_ratio
- zone_id
- zone_low
- zone_high
- zone_score
- zone_quality
- zone_member_count
- freshness
- data_quality
```

### Seviye yorumlama kurallari

1. Fiyat MA uzerindeyse MA destek adayi; altindaysa direnc adayi olabilir.
2. Yakinlik tek basina destek/direnc kaniti degildir.
3. Dusuk temas sayisi `Yetersiz veri` olarak kalir.
4. Yuksek gecmis tutma ve tepki, dusuk crossing ve saglam plateau daha guclu seviye kanitidir.
5. Birbirine yakin MA'lar ayri ayri raporlanmak yerine ATR tabanli tek confluence bolgesinde birlestirilir.
6. Ayni bolgede birden fazla MA ailesi/zaman dilimi varsa bu confluence metadata olarak tutulur; keyfi sekilde olasiliga cevrilmez.
7. Uzak MA bolgesi `STRUCTURAL`; orta uzaklik `SECONDARY`; fiyata yakin ve yeterli kaliteye sahip bolge `NEAR_TERM` olabilir.
8. Kırılmış MA seviyesi eski rolüyle pending tetik kalamaz; lifecycle/role-change mantigi uygulanir.

## 3. Rapor bolumu — Tarama ve Destek/Direnc Haritasi

Tam hisse raporunda teknik bolum su sirayla ilerler:

```text
A. Fiyat ve Piyasa Yapisi
B. Trend ve Ortalamalar
C. Momentum
D. Hacim / Katilim
E. Taramabot Sinyalleri
F. Dinamik MA Destek/Direnc Taramasi
G. Swing / BOS / CHoCH / Volume Profile / VWAP Seviyeleri
H. Birlesik Teknik Seviye Haritasi
I. Teknik Bolum Yorumu
```

### Ornek sunum

```text
DINAMIK DESTEK / DIRENC TARAMASI

1G destek bolgesi  : 20.80-21.15
Kaynak              : EMA50 + KAMA55
Bolge kalitesi      : Guclu
Gecmis temas        : 14
Tutma orani         : %79
Medyan tepki        : 1.6 ATR
Fiyata uzaklik      : 0.24 ATR

4S destek bolgesi   : 20.35-20.48
Kaynak              : EMA100 + SMA89
Bolge kalitesi      : Orta

1G direnc bolgesi   : 23.10-23.55
Kaynak              : SMA200 + ALMA200
Bolge kalitesi      : Guclu
```

Bu tablo `ma-reaction-scanner` kaynakli gozlemsel MA seviyelerini anlatir. Swing/structure seviyeleri ayri tutulur.

## 4. Birlesik Level Engine

Nihai teknik seviye havuzu:

```text
TechnicalLevel.source_family =
- STRUCTURE_SWING
- BOS_CHOCH
- MA_OBSERVED_LEVEL
- VWAP_AVWAP
- VOLUME_PROFILE
- PREVIOUS_PERIOD
- BOLLINGER
- ELLIOTT
- FIBONACCI
```

Her seviye ayni canonical alanlara normalize edilir:

```text
value / zone_low / zone_high
role
lifecycle_state
distance_pct
distance_atr
age_bars
priority
actionability
confidence
evidence_count
source_metadata
```

`priority` olasilik degildir. Yalniz sunum/siralama onceligidir.

## 5. Zaman dilimi kurali

Taramabot sinyali ve MA seviyesi mutlaka kendi timeframe etiketi ile korunur. Bir 15 dakikalik AL taramasi günlük trend dönüşü gibi yazilamaz; günlük MA direnci de 15 dakikalik scalp seviyesi gibi sunulamaz.

Onerilen hiyerarsi:

```text
5m / 15m / 30m -> cok kisa vade
1h / 2h / 4h   -> kisa vade
1d             -> ana swing / orta vade
1wk / 1mo      -> uzun vade / yapisal
```

Bu etiketler kullanici dilini yonlendirir, mekanik AL/SAT agirligi vermez.

## 6. Celiski matrisi

Sentez motoru celiskileri gizlemez.

Ornekler:

```text
Taramabot AL + fiyat guclu MA destegi uzerinde + BOS yok
=> erken toparlanma; yapi teyidi eksik

Taramabot AL + guclu MA direnci hemen ustte
=> momentum olumlu; yakin arz/direnc nedeniyle teyit sinirli

Taramabot SAT + gunluk ana destek korunuyor
=> kisa vade zayiflama; ana yapi henuz bozulmamis

Taramabot SAT + gunluk destek kirilmis + MA destekleri dirence donmus
=> teknik bozulma birden fazla bagimsiz kanitla uyumlu
```

## 7. Tam analiz sentezi

Teknik bolum kendi sonucunu üretir. Temel analiz, degerleme ve sirket olaylari ayri sonuc üretir. En son `EquityAnalysisState` bunlari birlestirir:

```text
EquityAnalysisState
- technical_state
  - structure
  - indicators
  - scanner_evidence
  - ma_level_evidence
  - unified_levels
  - technical_interpretation
- fundamental_state
- valuation_state
- corporate_events
- risks
- catalysts
- overall_interpretation
- confidence
- limitations
```

Genel yorum tek puana indirgenmez. Ornek:

```text
Teknik yapi      : Gecis / zayif
Momentum         : Iyilesiyor
Taramabot        : AL adayi (4s)
MA S/R            : Gunluk destek yakin, gunluk ana direnc uzak
Temel kalite     : Guclu
Degerleme        : Iskontolu
Genel            : Temel taraf destekleyici; teknik toparlanma erken evrede ve yapi teyidi eksik.
```

## 8. Entegrasyon stratejisi

1. Taramabot gelisirken burada yalnız `ScanSignal` adapter contract hazirlanir.
2. MA reaction icin `MALevelEvidence` adapter contract hazirlanir.
3. Repo-to-repo Python import yapilmaz.
4. İlk entegrasyon artifact/JSON okuyarak yapilir.
5. Formuller kararlilastiginda ortak `market_core` paketi veya versioned shared library dusunulur.
6. Kaynak versiyonu her raporda saklanir; sonradan hangi formulle üretildigi audit edilebilir.

Bu yaklasim iki kaynak repodaki gelistirmeyi durdurmadan tam analiz motorunun onlardan yararlanmasini saglar.