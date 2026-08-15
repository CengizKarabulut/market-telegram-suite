from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _number(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    return "—" if not math.isfinite(number) else f"{number:,.{digits}f}"


def _ma_group_text(context: dict[str, Any]) -> str:
    groups = context.get("ma_structure", {}).get("groups", {})
    parts = []
    for name in ("Çok kısa", "Kısa", "Orta", "Uzun"):
        item = groups.get(name)
        if item:
            parts.append(f"{name} {item.get('above', 0)}/{item.get('total', 0)} üstünde")
    return ", ".join(parts) if parts else "MA grup verisi yok"


def _direction(context: dict[str, Any], row: pd.Series) -> tuple[str, str]:
    structure = context.get("structure", {}).get("state", "Yetersiz pivot")
    if structure == "HH / HL":
        return "Yukarı yönlü dış yapı", "positive"
    if structure == "LH / LL":
        return "Aşağı yönlü dış yapı", "negative"
    groups = context.get("ma_structure", {}).get("groups", {})
    long_group = groups.get("Uzun", {})
    above = int(long_group.get("above", 0))
    total = int(long_group.get("total", 0))
    dmi_bullish = _number(row.get("PLUS_DI")) > _number(row.get("MINUS_DI"))
    if total and above == total and dmi_bullish:
        return "Uzun ortalamalar ve DMI yukarı eğilimli", "positive"
    if total and above == 0 and not dmi_bullish:
        return "Uzun ortalamalar ve DMI aşağı eğilimli", "negative"
    return "Yön teyidi karışık", "warning"


def _regime_text(regime: str, direction: str, adx: float, adx_delta: float) -> tuple[str, str, str]:
    if "Denge" in regime or "sıkışma" in regime:
        return (
            "Denge / teyit bekliyor",
            "warning",
            f"{regime}: trend takip kesişimleri gürültülü olabilir; {direction.lower()}. Yeni hareket için bant genişlemesi, seviye kabulü ve hacim teyidi aranmalı.",
        )
    if "Volatilite genişlemesi" in regime:
        return (
            "Yönsüz volatilite genişlemesi",
            "warning",
            f"Volatilite genişliyor ancak yönlülük zayıf; ADX {_fmt(adx)}. {direction} tek başına kırılım teyidi değildir.",
        )
    if regime.startswith(("Trend", "Yönlü")):
        strength = "güç kazanıyor" if adx_delta > 0 else "güç kaybediyor" if adx_delta < 0 else "yatay"
        tone = "positive" if "Yukarı" in direction else "negative" if "Aşağı" in direction else "warning"
        return (
            f"{direction} / {regime}",
            tone,
            f"{regime}; ADX {_fmt(adx)} ve son değişimi {adx_delta:+.2f}, yani yönlülük {strength}. {direction}.",
        )
    return (
        "Geçiş / çelişkili bağlam",
        "warning",
        f"{regime}; {direction.lower()}. Yapı, momentum ve katılım aynı yönde teyit vermeden tek göstergeye dayalı yorum zayıf kalır.",
    )


def _momentum_text(data: pd.DataFrame, context: dict[str, Any]) -> tuple[str, int]:
    row = data.iloc[-1]
    previous = data.iloc[-2]
    rsi = _number(row.get("RSI"))
    rsi_ma = _number(row.get("RSI_MA"))
    macd = _number(row.get("MACD"))
    signal = _number(row.get("MACD_SIGNAL"))
    histogram = _number(row.get("MACD_HIST"))
    previous_histogram = _number(previous.get("MACD_HIST"))
    smi = _number(row.get("SMI"))
    smi_signal = _number(row.get("SMI_EMA"))
    stoch_k = _number(row.get("STOCH_K"))
    stoch_d = _number(row.get("STOCH_D"))
    relations = [macd > signal, rsi > rsi_ma, stoch_k > stoch_d, smi > smi_signal]
    positive = sum(relations)
    if histogram < 0:
        histogram_text = "negatif histogram daralıyor" if histogram > previous_histogram else "negatif histogram genişliyor"
    elif histogram > 0:
        histogram_text = "pozitif histogram genişliyor" if histogram > previous_histogram else "pozitif histogram daralıyor"
    else:
        histogram_text = "histogram sıfırda"
    active = [
        f"{name} {item['state']} ({item['event_age']} bar)"
        for name, item in context.get("divergences", {}).get("indicators", {}).items()
        if item.get("detected")
    ]
    divergence_text = "; aktif " + " | ".join(active) if active else "; son 5 barda aktif uyumsuzluk yok"
    summary = (
        f"RSI {_fmt(rsi)} ({'50 üstü' if rsi >= 50 else '50 altı'}, MA14 {'üstü' if rsi > rsi_ma else 'altı'}); "
        f"MACD {'sinyal üstü' if macd > signal else 'sinyal altı'} ve {'0 üstü' if macd > 0 else '0 altı'}, {histogram_text}; "
        f"SMI {'sinyal üstü' if smi > smi_signal else 'sinyal altı'}{divergence_text}. "
    )
    summary += "RSI, MACD, Stoch RSI ve SMI aynı momentum ailesindedir; bağımsız oylar gibi sayılmaz."
    return summary, positive


def _volatility_text(data: pd.DataFrame, context: dict[str, Any]) -> tuple[str, bool]:
    row = data.iloc[-1]
    previous = data.iloc[-2]
    bb_rank = _number(row.get("BB_WIDTH_RANK"))
    atr_rank = _number(row.get("ATR_RANK"))
    widening = _number(row.get("BB_WIDTH")) > _number(previous.get("BB_WIDTH"))
    squeeze = bb_rank <= 20
    if squeeze and widening:
        state = "Bantlar hâlâ dar bölgede ancak genişleme denemesi var"
    elif squeeze:
        state = "Bollinger sıkışması sürüyor; yön henüz belli değil"
    elif bb_rank >= 80:
        state = "Bantlar tarihsel olarak geniş; geç kırılım ve sert geri dönüş riski artmış olabilir"
    else:
        state = "Volatilite orta bölgede ve bantlar " + ("genişliyor" if widening else "daralıyor")
    return f"{state}. BB genişlik yüzdeliği %{_fmt(bb_rank, 0)}, ATR yüzdeliği %{_fmt(atr_rank, 0)}.", squeeze


def _participation_text(data: pd.DataFrame, context: dict[str, Any]) -> tuple[str, str]:
    row = data.iloc[-1]
    previous = data.iloc[-2]
    rvol = _number(context.get("relative_volume"))
    change = (_number(row.get("Close")) / _number(previous.get("Close")) - 1) * 100
    if abs(change) <= 0.5 and rvol >= 1.5:
        state = "Fiyat az ilerlerken yüksek hacim var; absorption/mücadele olasılığı yalnız OHLCV proxy olarak izlenmeli"
        tone = "warning"
    elif change > 0 and rvol >= 1.1:
        state, tone = "Yükseliş ortalama üstü katılımla destekleniyor", "positive"
    elif change > 0:
        state, tone = "Yükselişte katılım zayıf", "warning"
    elif change < 0 and rvol >= 1.1:
        state, tone = "Düşüşe ortalama üstü hacim eşlik ediyor", "negative"
    else:
        state, tone = "Düşüş var ancak satış katılımı düşük", "warning"
    obv_direction = "yükseldi" if _number(row.get("OBV")) > _number(previous.get("OBV")) else "düştü"
    return f"RVOL {rvol:.2f}x; {state}. OBV son barda {obv_direction}.", tone


def _location_text(context: dict[str, Any], price: float) -> str:
    profile = context.get("profile", {})
    vwaps = context.get("anchored_vwaps", {})
    manual = _number(vwaps.get("manual"))
    avwap_relation = "üzerinde" if math.isfinite(manual) and price > manual else "altında" if math.isfinite(manual) else "hesaplanamadı"
    return (
        f"Fiyat {profile.get('position', 'profil konumu yok')}; {profile.get('developing_acceptance', 'kabul verisi yok')}. "
        f"POC {_fmt(profile.get('poc'))}, VAH {_fmt(profile.get('vah'))}, VAL {_fmt(profile.get('val'))}; "
        f"fiyat AVWAP {_fmt(manual)} {avwap_relation}. POC göçü: {profile.get('poc_migration', '—')}."
    )


def _relative_text(decision: dict[str, Any]) -> str:
    rs = decision.get("relative_strength", {})
    mtf = decision.get("multi_timeframe", {})
    liquidity = decision.get("liquidity", {})
    rs_text = f"{rs.get('state', 'Benchmark verisi yok')} ({rs.get('benchmark', '—')})"
    return f"Göreceli güç: {rs_text}. MTF: {mtf.get('state', '—')}. Likidite: {liquidity.get('state', '—')}."


def _watch_items(context: dict[str, Any], squeeze: bool) -> list[str]:
    profile = context.get("profile", {})
    structure = context.get("structure", {})
    position = str(profile.get("position", ""))
    vah, val = _number(profile.get("vah")), _number(profile.get("val"))
    items: list[str] = []
    if "içinde" in position:
        items.append(f"VAH {_fmt(vah)} üstünde kapanış + developing kabul + RVOL artışı yukarı genişlemeyi destekler; VAL {_fmt(val)} altı kabul aşağı riski artırır.")
    elif "üzerinde" in position:
        items.append(f"VAH {_fmt(vah)} üzerinde kalıcılık izlenmeli; Value Area içine dönüş mevcut yukarı kabulü zayıflatır.")
    elif "altında" in position:
        items.append(f"VAL {_fmt(val)} geri kazanımı izlenmeli; VAL altında kalıcılık aşağı kabulün sürdüğünü gösterir.")
    high, low = _number(structure.get("high")), _number(structure.get("low"))
    if math.isfinite(high) and math.isfinite(low):
        items.append(f"Teyitli swing aralığı {_fmt(low)}–{_fmt(high)}; kapanışla kırılım ve sonrasındaki retest, fitil aşımından daha güçlü kanıttır.")
    if squeeze:
        items.append("Sıkışma tek başına yön vermez; BB genişlemesi, kapanışla seviye kırılımı ve RVOL teyidi birlikte izlenmeli.")
    active = [item for item in context.get("divergences", {}).get("indicators", {}).values() if item.get("detected")]
    if active:
        items.append("Aktif uyumsuzluk erken uyarıdır; yapı kırılımı veya seviye reclaim/rejection olmadan dönüş teyidi sayılmaz.")
    return items[:3] or ["Yeni teyit için yapı kırılımı, seviye kabulü ve katılım birlikte izlenmeli."]


def build_technical_commentary(
    data: pd.DataFrame,
    context: dict[str, Any],
    decision: dict[str, Any],
    bar_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = data.iloc[-1]
    price = _number(row.get("Close"))
    direction, direction_tone = _direction(context, row)
    regime = str(context.get("regime", {}).get("state", "Bilinmeyen rejim"))
    adx = _number(context.get("regime", {}).get("adx"))
    adx_delta = _number(context.get("regime", {}).get("adx_delta"), 0.0)
    stance, tone, headline = _regime_text(regime, direction, adx, adx_delta)
    trend = f"{_ma_group_text(context)}. +DI {_fmt(row.get('PLUS_DI'))}, -DI {_fmt(row.get('MINUS_DI'))}, ADX {_fmt(adx)}; dış yapı {context.get('structure', {}).get('state', '—')}."
    momentum, momentum_positive = _momentum_text(data, context)
    volatility, squeeze = _volatility_text(data, context)
    participation, participation_tone = _participation_text(data, context)
    location = _location_text(context, price)
    relative = _relative_text(decision)

    conflicts: list[str] = []
    dmi_bullish = _number(row.get("PLUS_DI")) > _number(row.get("MINUS_DI"))
    if direction_tone == "positive" and not dmi_bullish:
        conflicts.append("Yukarı yapı varken -DI üstün; yön ile güncel directional pressure ayrışıyor.")
    if direction_tone == "negative" and dmi_bullish:
        conflicts.append("Aşağı yapı varken +DI üstün; kısa vadeli tepki ile ana yapı ayrışıyor.")
    if direction_tone == "positive" and momentum_positive <= 1:
        conflicts.append("Yukarı bağlama rağmen momentum ailesi aşağı ağırlıklı.")
    if direction_tone == "negative" and momentum_positive >= 3:
        conflicts.append("Aşağı bağlama rağmen momentum ailesi yukarı ağırlıklı.")
    rs_tone = decision.get("relative_strength", {}).get("tone")
    if direction_tone == "positive" and rs_tone == "negative":
        conflicts.append("Fiyat yapısı yukarı olsa da hisse benchmarka göre zayıflıyor.")
    if direction_tone == "negative" and rs_tone == "positive":
        conflicts.append("Fiyat yapısı aşağı olsa da benchmarka göre göreceli güçlenme var.")
    if decision.get("multi_timeframe", {}).get("tone") == "warning":
        conflicts.append("Günlük/haftalık/aylık zaman dilimleri aynı yönde değil.")
    if _number(context.get("relative_volume")) < 0.8:
        conflicts.append("RVOL 0,8x altında; mevcut hareketin katılım teyidi zayıf.")
    if bar_state and bar_state.get("is_live"):
        conflicts.append("Son mum CANLI; kapanışa kadar gösterge, yapı ve kabul durumu değişebilir.")
    conflicts = conflicts[:4]
    conflict_text = " ".join(conflicts) if conflicts else "Ana katmanlar arasında belirgin bir çelişki saptanmadı; yine de tetikleyici ve kapanış teyidi gerekir."
    watch = _watch_items(context, squeeze)
    evidence = [trend, momentum, volatility, participation, location, relative]
    visual_rows = [
        ["Ana okuma", stance, headline, tone],
        ["Trend / yapı", direction, trend, direction_tone],
        ["Momentum / katılım", f"{momentum_positive}/4 ilişki üstte", f"{momentum} {participation}", participation_tone],
        ["Konum / volatilite", context.get("profile", {}).get("position", "—"), f"{location} {volatility}", "warning" if squeeze else "neutral"],
        ["Çelişki / teyit", f"{len(conflicts)} karşı kanıt", f"{conflict_text} İzlenecek: {watch[0]}", "warning" if conflicts else "neutral"],
    ]
    telegram_summary = f"{headline} İzlenecek: {watch[0]}"
    return {
        "stance": stance,
        "tone": tone,
        "headline": headline,
        "direction": direction,
        "regime": regime,
        "evidence": evidence,
        "conflicts": conflicts,
        "watch": watch,
        "visual_rows": visual_rows,
        "telegram_summary": telegram_summary,
        "framework": ["Regime", "Direction", "Location", "Setup", "Trigger", "Confirmation", "Risk", "Exit"],
        "method": "Deterministik katmanlı yorum; birleşik AL/SAT puanı üretmez. Korelasyonlu momentum göstergeleri bağımsız oy sayılmaz.",
        "limitations": [
            "Yorum yalnız mevcut OHLCV ve türetilmiş teknik bağlama dayanır; haber/KAP/temel veri içermez.",
            "Volume Profile ve delta alanları yaklaşık OHLCV proxy'dir; gerçek footprint değildir.",
            "CANLI mum kapanışa kadar değişebilir; uyumsuzluk ve swingler sağ pivot barları tamamlanınca teyit edilir.",
        ],
    }
