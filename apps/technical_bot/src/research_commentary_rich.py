"""Richer analyst commentary contract for /analiz.

All non-technical sections reuse the audited deterministic commentary composer.
The technical paragraph is expanded with multi-timeframe structure, BOS/CHoCH,
AlphaTrend, Bollinger, MACD, SMI, RSI divergence, OBV, RVOL, ATR and conservative
Elliott context. Missing values are stated as missing instead of inferred.
"""

from __future__ import annotations

from src import research_commentary as base
from src.research_engine import ResearchReport


def _zone(value: float | None, *, upper: float, lower: float, high: str, low: str) -> str:
    if value is None:
        return "veri yetersiz"
    if value >= upper:
        return high
    if value <= lower:
        return low
    return "nötr bölge"


def _direction(value: float | None, signal: float | None) -> str:
    if value is None or signal is None:
        return "sinyal karşılaştırması için veri yetersiz"
    if value > signal:
        return "sinyal çizgisinin üzerinde"
    if value < signal:
        return "sinyal çizgisinin altında"
    return "sinyal çizgisiyle aynı seviyede"


def _technical_paragraph_rich(report: ResearchReport) -> str:
    technical = report.technical
    structure = technical.get("structure", {})
    weekly = technical.get("weekly_structure", {})
    monthly = technical.get("monthly_structure", {})
    elliott = technical.get("elliott", {})

    score = base._finite(technical.get("score"))
    score_text = "—" if score is None else f"{score:.0f}/100"
    label = str(technical.get("label", "VERİ YETERSİZ")).casefold()

    rsi = base._finite(technical.get("rsi14"))
    smi = base._finite(technical.get("smi"))
    smi_signal = base._finite(technical.get("smi_signal"))
    macd_hist = base._finite(technical.get("macd_hist"))
    obv_change = base._finite(technical.get("obv_10d_change"))
    rvol = base._finite(technical.get("rvol20"))
    atr_pct = base._finite(technical.get("atr_pct"))
    divergence = technical.get("latest_rsi_divergence")
    divergence_text = divergence.get("kind") if isinstance(divergence, dict) else "yok"

    rsi_zone = _zone(
        rsi,
        upper=70.0,
        lower=30.0,
        high="aşırı alım bölgesi",
        low="aşırı satım bölgesi",
    )
    smi_zone = _zone(
        smi,
        upper=40.0,
        lower=-40.0,
        high="+40 üzeri aşırı alım bölgesi",
        low="-40 altı aşırı satım bölgesi",
    )
    macd_state = (
        "veri yetersiz"
        if macd_hist is None
        else "pozitif histogram"
        if macd_hist > 0
        else "negatif histogram"
        if macd_hist < 0
        else "sıfır histogram"
    )
    volume_state = (
        "RVOL verisi yetersiz"
        if rvol is None
        else f"RVOL20 {rvol:.2f}x ile olağanın üzerinde hacim"
        if rvol >= 1.5
        else f"RVOL20 {rvol:.2f}x ile normal hacim"
        if rvol >= 0.8
        else f"RVOL20 {rvol:.2f}x ile zayıf hacim"
    )
    volatility_state = (
        "ATR verisi yetersiz"
        if atr_pct is None
        else f"ATR %{atr_pct:.1f} ile yüksek volatilite"
        if atr_pct >= 5.0
        else f"ATR %{atr_pct:.1f} ile orta volatilite"
        if atr_pct >= 2.5
        else f"ATR %{atr_pct:.1f} ile görece düşük volatilite"
    )
    obv_text = "—" if obv_change is None else f"%{obv_change:+.1f}"

    invalidation = base._finite(elliott.get("invalidation"))
    invalidation_text = "—" if invalidation is None else f"{invalidation:,.2f}"
    confidence = base._finite(elliott.get("confidence"))
    confidence_text = "—" if confidence is None else f"%{confidence:.0f}"

    return (
        f"Teknik yapı {score_text} ile {label}. Günlük piyasa yapısında {structure.get('state', '—')} ve "
        f"{structure.get('event', structure.get('bos', '—'))}; haftalık {weekly.get('state', '—')} / "
        f"{weekly.get('event', '—')}, aylık {monthly.get('state', '—')} / {monthly.get('event', '—')} okunuyor. "
        f"AlphaTrend {technical.get('alpha_trend_state', '—')}; Bollinger konumu "
        f"{technical.get('bollinger_state', '—')}. Momentum tarafında RSI {base._num(rsi)} ile {rsi_zone} ve son "
        f"regular uyumsuzluk {divergence_text}; SMI {base._num(smi)} ({smi_zone}, {_direction(smi, smi_signal)}), "
        f"MACD {macd_state}; OBV 10 günlük değişim {obv_text}. Hacim/volatilite tarafında {volume_state} ve "
        f"{volatility_state}. Elliott bağlamı {elliott.get('primary', '—')}; alternatif "
        f"{elliott.get('alternate', '—')}, güven {confidence_text}, invalidation {invalidation_text}. Bu göstergeler "
        "tek başına işlem çağrısı olarak değil, HH/HL/LH/LL, BOS/CHoCH ve kritik seviye yaşam döngüsünü teyit "
        "veya zayıflatmak için birlikte okunuyor."
    )


def compose_research_commentary(report: ResearchReport) -> tuple[tuple[str, str], ...]:
    """Return the agreed analyst sections in the user-facing order."""
    return (
        ("ŞİRKET NE DURUMDA?", base._company_paragraph(report)),
        ("DEĞERLEME NASIL?", base._valuation_paragraph(report)),
        ("BİLANÇO İYİLEŞİYOR MU?", base._balance_paragraph(report)),
        ("KÂR KALİTELİ Mİ?", base._earnings_paragraph(report)),
        ("BORÇ VE NAKİT NE YÖNDE?", base._debt_paragraph(report)),
        ("TEKNİK YAPI NE DİYOR?", _technical_paragraph_rich(report)),
        ("KRİTİK SEVİYELER NEREDE?", base._levels_paragraph(report)),
        ("ASIL RİSK NE?", base._risk_paragraph(report)),
        ("SONUÇ", base._conclusion_paragraph(report)),
    )


def commentary_messages(report: ResearchReport, limit: int = 3900) -> tuple[str, ...]:
    """Split the ordered paragraphs only at section boundaries."""
    blocks = [f"📌 {title}\n{paragraph}" for title, paragraph in compose_research_commentary(report)]
    messages: list[str] = []
    current = f"🧾 {report.symbol} — ANALİST YORUMU"
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue
        messages.append(current)
        current = block
    if current:
        messages.append(current)
    return tuple(messages)
