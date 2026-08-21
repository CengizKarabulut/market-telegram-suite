from __future__ import annotations

import math
import re
from typing import Any

import pandas as pd

from src.plain_language import build_plain_summary
from src.setup_recognition import evidence_weight, reconcile
from src.state_change import compare_states


def _number(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _fmt(value: Any, digits: int = 2) -> str:
    number = _number(value)
    return "—" if not math.isfinite(number) else f"{number:,.{digits}f}"


def _direction(context: dict[str, Any]) -> tuple[str, str]:
    """Yönü yapıdan uzatmak yerine tanınan kurulumun eğiliminden türetir."""
    setup = context.get("setup_context", {}).get("setup", {})
    bias = str(setup.get("bias", ""))
    structure = context.get("structure", {}).get("state", "Yetersiz pivot")
    if bias == "yukarı":
        return f"{setup.get('name', 'Yukarı kurulum')} — yukarı eğilimli", "positive"
    if bias == "aşağı":
        return f"{setup.get('name', 'Aşağı kurulum')} — aşağı eğilimli", "negative"
    if bias == "iki yönlü":
        return f"{setup.get('name', 'Koşullu kurulum')} — koşullu", "warning"
    if structure == "HH / HL":
        return "Yukarı yönlü yapı", "positive"
    if structure == "LH / LL":
        return "Aşağı yönlü yapı", "negative"
    return "Yön teyidi karışık", "warning"


def _regime_opening(regime: str, direction: str, adx: float, adx_delta: float) -> tuple[str, str, str]:
    if "sıkışma" in regime.casefold() or "denge" in regime.casefold():
        return (
            "Denge / teyit bekliyor",
            "warning",
            f"Piyasa {regime.casefold()} rejiminde. Daralan hareket alanında gösterge kesişimlerinin bilgi değeri düşer; yeni yön için bant genişlemesi, kapanışla seviye kabulü ve hacim teyidi gerekir.",
        )
    if "yönsüz" in regime.casefold():
        return (
            "Yönsüz volatilite / seçicilik gerekli",
            "warning",
            f"Volatilite genişliyor fakat yönlülük zayıf; ADX {_fmt(adx)}. Mevcut sınıflama tek başına kalıcı kırılım teyidi değildir.",
        )
    if regime.startswith(("Trend", "Yönlü")):
        strength = "güç kazanıyor" if adx_delta > 0 else "güç kaybediyor" if adx_delta < 0 else "yatay"
        tone = "positive" if direction.startswith(("Yukarı", "Ortalamalar yukarı")) else "negative" if direction.startswith(("Aşağı", "Ortalamalar aşağı")) else "warning"
        return (
            f"{direction} / {regime}",
            tone,
            f"{regime}; ADX {_fmt(adx)} ve bir barlık değişimi {adx_delta:+.2f}, yani yönlülük {strength}.",
        )
    return (
        "Geçiş / çelişkili bağlam",
        "warning",
        f"{regime}. Yapı, momentum ve katılım aynı yönde teyit vermeden tek bir göstergeye dayalı okuma zayıf kalır.",
    )


def _rs_text(decision: dict[str, Any]) -> tuple[str, str, str]:
    rs = decision.get("relative_strength", {})
    if not rs.get("available"):
        return "Benchmark verisi yok", "warning", "Göreceli güç karşılaştırması yapılamadı."
    period = rs.get("periods", {}).get("20", {})
    stock_return = _number(period.get("stock_return_pct"))
    benchmark_return = _number(period.get("benchmark_return_pct"))
    excess = _number(period.get("excess_return_pct"))
    slope = _number(rs.get("ratio_slope_5_pct"))
    meaning = (
        f"Son 20 barda hisse %{stock_return:+.2f}, {rs.get('benchmark', 'benchmark')} %{benchmark_return:+.2f}; "
        f"göreceli fark {excess:+.2f} puan ve rasyo 5 bar eğimi %{slope:+.2f}. "
        "Bu relatif performanstır; doğrudan fon akışı ölçümü değildir."
    )
    return str(rs.get("state", "Göreceli güç karışık")), str(rs.get("tone", "warning")), meaning


def _location_text(context: dict[str, Any]) -> str:
    profile = context.get("profile", {})
    confluence = context.get("semantic", {}).get("level_confluence", {})
    nearest = confluence.get("summary", "Yakın teknik seviye bulunamadı.")
    clusters = confluence.get("clusters", [])
    cluster_text = ""
    if clusters:
        cluster = clusters[0]
        names = ", ".join(cluster["members"][:5])
        cluster_text = f" En yakın yoğunlaşma {_fmt(cluster['low'])}–{_fmt(cluster['high'])} ({names}, {cluster['strength'].casefold()})."
    return (
        f"Fiyat {profile.get('position', 'profil konumu yok')}; {profile.get('developing_acceptance', 'kabul verisi yok')}. "
        f"POC göçü {profile.get('poc_migration', '—')}. {nearest}{cluster_text}"
    )


def _technical_levels(context: dict[str, Any], direction_tone: str) -> dict[str, Any]:
    confluence = context.get("semantic", {}).get("level_confluence", {})
    structure = context.get("structure", {})
    support = confluence.get("nearest_support")
    resistance = confluence.get("nearest_resistance")
    if direction_tone == "positive" and math.isfinite(_number(structure.get("low"))):
        invalidation = f"{_fmt(structure['low'])} altında günlük kapanış mevcut yukarı yapıyı geçersizleştirir."
        invalidation_level = _number(structure["low"])
    elif direction_tone == "negative" and math.isfinite(_number(structure.get("high"))):
        invalidation = f"{_fmt(structure['high'])} üzerinde günlük kapanış mevcut aşağı yapıyı geçersizleştirir."
        invalidation_level = _number(structure["high"])
    else:
        invalidation = "Yapı karışık olduğu için tek bir teknik geçersizlik seviyesi tanımlanmadı."
        invalidation_level = None
    return {
        "nearest_support": support,
        "nearest_resistance": resistance,
        "clusters": confluence.get("clusters", []),
        "invalidation": invalidation,
        "invalidation_level": invalidation_level,
        "method": "Seviyeler izleme referansıdır; emir veya stop önerisi değildir.",
    }


def _changes(data: pd.DataFrame, context: dict[str, Any]) -> list[str]:
    """Okumanın kendisi düne göre nasıl değişti?

    Önceki bar için yeniden hesaplanmış durum varsa alan alan karşılaştırma
    yapılır. Yoksa yalnızca temel gösterge geçişlerine düşülür.
    """
    comparison = compare_states(context.get("previous_state"), context)
    if comparison["available"]:
        context["state_comparison"] = comparison
        return comparison["bullets"]
    row = data.iloc[-1]
    previous = data.iloc[-2]
    changes: list[str] = []
    if previous["RSI"] < 50 <= row["RSI"]:
        changes.append(f"RSI 50 seviyesini geri kazandı ({previous['RSI']:.1f} → {row['RSI']:.1f}).")
    elif previous["RSI"] >= 50 > row["RSI"]:
        changes.append(f"RSI 50 seviyesinin altına indi ({previous['RSI']:.1f} → {row['RSI']:.1f}).")
    if previous["MACD_HIST"] <= 0 < row["MACD_HIST"]:
        changes.append("MACD histogramı negatiften pozitife geçti.")
    elif previous["MACD_HIST"] >= 0 > row["MACD_HIST"]:
        changes.append("MACD histogramı pozitiften negatife geçti.")
    if previous["SMI"] <= previous["SMI_EMA"] and row["SMI"] > row["SMI_EMA"]:
        changes.append("SMI sinyal çizgisini yukarı kesti.")
    elif previous["SMI"] >= previous["SMI_EMA"] and row["SMI"] < row["SMI_EMA"]:
        changes.append("SMI sinyal çizgisini aşağı kesti.")
    for event in context.get("events", []):
        if int(event.get("age", 99)) == 0 and event.get("event") not in " ".join(changes):
            changes.append(f"Yeni olay: {event['event']} ({event['state']}).")
    regime = context.get("regime", {})
    if regime.get("candidate") and regime.get("candidate") != regime.get("state"):
        changes.append(f"Rejim adayı {regime['candidate']}; kalıcı sınıflama için devam teyidi bekleniyor.")
    profile = context.get("profile", {})
    if profile.get("poc_migration") not in (None, "Yatay"):
        changes.append(f"POC {profile['poc_migration'].casefold()} davranışına geçti.")
    return changes[:5] or ["Son barda ana teknik sınıflamayı değiştiren yeni bir olay oluşmadı."]


def _threshold_distance(text: str, price: float) -> float:
    """Senaryo metnindeki seviyenin fiyata uzaklığını bulur; yakın eşikler öne alınır."""
    distances = []
    for token in re.findall(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?", text):
        cleaned = token.replace(",", "") if token.count(".") == 1 and "," in token else token.replace(",", ".")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        if price * 0.5 <= value <= price * 2.0:
            distances.append(abs(value - price) / price)
    return min(distances) if distances else math.inf


def _scenario_map(
    context: dict[str, Any],
    decision: dict[str, Any],
    direction_tone: str,
    levels: dict[str, Any],
) -> dict[str, list[str]]:
    profile = context.get("profile", {})
    structure = context.get("structure", {})
    semantic = context.get("semantic", {})
    participation = semantic.get("participation", {})
    strengthen: list[str] = []
    weaken: list[str] = []
    neutral: list[str] = []
    setup = context.get("setup_context", {}).get("setup", {})
    bias = str(setup.get("bias", ""))
    if bias == "iki yönlü":
        strengthen.append(f"{_fmt(structure.get('high'))} üzerinde kapanış: yukarı çözülme")
        strengthen.append(f"{_fmt(structure.get('low'))} altında kapanış: aşağı çözülme")
        weaken.append("Her iki uçta da kapanışla kabul oluşmadan aralık içinde kalınması")
    elif direction_tone == "positive":
        strengthen.append(f"{_fmt(structure.get('high'))} swing zirvesi üzerinde kapanış ve retest başarısı")
        weaken.append(levels["invalidation"])
    elif direction_tone == "negative":
        strengthen.append(f"{_fmt(structure.get('low'))} swing dibi altında kapanış ve aşağı kabul")
        weaken.append(levels["invalidation"])
    else:
        strengthen.append("Teyitli yapı kırılımıyla yönün netleşmesi")
        weaken.append("Kırılım denemesinin yeniden denge alanına dönmesi")
    if "içinde" in str(profile.get("position", "")):
        strengthen.append(f"VAH {_fmt(profile.get('vah'))} üzerinde veya VAL {_fmt(profile.get('val'))} altında kapanış + developing kabul")
        neutral.append(f"POC {_fmt(profile.get('poc'))} çevresinde düşük RVOL ile rotasyon")
    elif "üzerinde" in str(profile.get("position", "")):
        strengthen.append(f"VAH {_fmt(profile.get('vah'))} üzerinde kalıcılık ve RVOL artışı")
        weaken.append("Value Area içine geri dönüş")
    else:
        strengthen.append(f"VAL {_fmt(profile.get('val'))} altında kalıcılık ve RVOL artışı")
        weaken.append("Value Area içine geri kazanım")
    strengthen.append("Ana yönle uyumlu MACD histogram genişlemesi ve RVOL ≥ 1,10x")
    if _number(participation.get("rvol_1")) < 0.8:
        neutral.append("RVOL 0,80x altında kaldıkça hareketin katılım teyidinin sınırlı kalması")
    if "sıkışma" in str(context.get("regime", {}).get("state", "")).casefold():
        neutral.append("Bantlar genişlemeden ve kapanışla seviye kabulü oluşmadan sıkışmanın sürmesi")
    if decision.get("multi_timeframe", {}).get("tone") == "warning":
        weaken.append("Zaman dilimi ayrışmasının sürmesi")
    labels = (
        {"strengthen": "Yukarı/aşağı çözülme koşulları", "weaken": "Kurulumu geçersiz kılacak gelişmeler", "neutral": "Durumu koruyacak gelişmeler"}
        if bias == "iki yönlü"
        else {"strengthen": "Mevcut okumayı teyit edecek gelişmeler", "weaken": "Mevcut okumayı zayıflatacak gelişmeler", "neutral": "Durumu nötr tutacak gelişmeler"}
    )
    price = _number(context.get("last_price"))
    if math.isfinite(price):
        strengthen.sort(key=lambda item: _threshold_distance(item, price))
        weaken.sort(key=lambda item: _threshold_distance(item, price))
    return {"strengthen": strengthen[:3], "weaken": weaken[:3], "neutral": neutral[:3], "labels": labels}


def _evidence_and_clarity(
    context: dict[str, Any],
    decision: dict[str, Any],
    direction_tone: str,
    bar_state: dict[str, Any] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
    semantic = context.get("semantic", {})
    families = [
        ("Yapı", context.get("structure", {}).get("state", "—"), context.get("structure", {}).get("tone", "neutral")),
        ("Trend", semantic.get("trend_quality", {}).get("state", "—"), semantic.get("trend_quality", {}).get("tone", "neutral")),
        ("Momentum", semantic.get("momentum_character", {}).get("state", "—"), semantic.get("momentum_character", {}).get("tone", "neutral")),
        ("Katılım", semantic.get("participation", {}).get("state", "—"), semantic.get("participation", {}).get("tone", "neutral")),
        ("Konum", context.get("profile", {}).get("position", "—"), context.get("profile", {}).get("tone", "neutral")),
        ("Göreceli güç", decision.get("relative_strength", {}).get("state", "—"), decision.get("relative_strength", {}).get("tone", "neutral")),
        ("Fiyat davranışı", semantic.get("price_action", {}).get("state", "—"), semantic.get("price_action", {}).get("tone", "neutral")),
    ]
    setup = context.get("setup_context", {}).get("setup", {})
    if setup.get("name"):
        setup_evidence_tone = {"yukarı": "positive", "aşağı": "negative"}.get(str(setup.get("bias")), "")
        if not setup_evidence_tone and "aşağı kırılım" in str(setup["name"]).casefold():
            setup_evidence_tone = "positive"
        elif not setup_evidence_tone and "yukarı kırılım" in str(setup["name"]).casefold():
            setup_evidence_tone = "negative"
        if setup_evidence_tone:
            families.append(("Kurulum", setup["name"], setup_evidence_tone))
    for divergence in semantic.get("momentum_character", {}).get("active_divergences", []):
        if divergence.get("quality") not in {"Güçlü", "Orta"}:
            continue
        label = str(divergence.get("state", ""))
        divergence_tone = "positive" if "pozitif" in label.casefold() else "negative" if "negatif" in label.casefold() else ""
        if divergence_tone:
            families.append((
                f"Uyumsuzluk ({divergence.get('indicator', '—')})",
                f"{label} — {divergence.get('quality', '—')} kalite",
                divergence_tone,
            ))
    supporting: list[dict[str, str]] = []
    counter: list[dict[str, str]] = []
    two_sided = str(context.get("setup_context", {}).get("setup", {}).get("bias", "")) == "iki yönlü"
    for family, state, tone in families:
        item = {"family": family, "state": str(state), "tone": str(tone)}
        if two_sided:
            if tone == "positive":
                supporting.append(item)
            elif tone == "negative":
                counter.append(item)
        elif tone == direction_tone:
            supporting.append(item)
        elif tone in {"positive", "negative"} and direction_tone in {"positive", "negative"}:
            counter.append(item)
    if decision.get("multi_timeframe", {}).get("tone") == "warning":
        counter.append({"family": "MTF", "state": "Günlük/haftalık/aylık yönler tam uyumlu değil", "tone": "warning"})
    if bar_state and bar_state.get("is_live"):
        counter.append({"family": "Bar", "state": "Son mum CANLI; kapanışa kadar sınıflamalar değişebilir", "tone": "warning"})
    regime = str(context.get("regime", {}).get("state", ""))
    supporting_weight = sum(evidence_weight(regime, item["family"]) for item in supporting)
    counter_weight = sum(evidence_weight(regime, item["family"]) for item in counter)
    supporting.sort(key=lambda item: evidence_weight(regime, item["family"]), reverse=True)
    counter.sort(key=lambda item: evidence_weight(regime, item["family"]), reverse=True)
    if two_sided:
        upward_weight, downward_weight = supporting_weight, counter_weight
        total = upward_weight + downward_weight
        weight_note = f"Rejime göre ağırlıklı yukarı kanıt {upward_weight:.1f}, aşağı kanıt {downward_weight:.1f}."
        dominant = max(upward_weight, downward_weight)
        if total == 0:
            clarity = {"state": "Düşük", "tone": "warning", "reason": f"Hiçbir katman belirgin yön üretmiyor. {weight_note}"}
        elif dominant / total >= 0.75:
            side = "yukarı" if upward_weight > downward_weight else "aşağı"
            clarity = {
                "state": "Orta",
                "tone": "neutral",
                "reason": f"Kanıtlar {side} tarafta yoğunlaşıyor fakat kurulum kapanışla teyit beklediği için okuma koşullu kalıyor. {weight_note}",
            }
        else:
            clarity = {"state": "Düşük", "tone": "warning", "reason": f"Kanıtlar iki yöne dağılmış durumda. {weight_note}"}
    else:
        weight_note = f"Rejime göre ağırlıklı kanıt {supporting_weight:.1f}, karşı kanıt {counter_weight:.1f}."
        if counter_weight <= 1.0 and supporting_weight >= 4.0:
            clarity = {"state": "Yüksek", "tone": "positive", "reason": f"Rejimde ağırlığı yüksek aileler aynı yönde. {weight_note}"}
        elif counter_weight >= supporting_weight * 0.8:
            clarity = {"state": "Düşük", "tone": "warning", "reason": f"Rejimde ağırlığı yüksek aileler belirgin biçimde ayrışıyor. {weight_note}"}
        else:
            clarity = {"state": "Orta", "tone": "neutral", "reason": f"Ana okuma mevcut ancak bazı katmanlar teyidi sınırlıyor. {weight_note}"}
    clarity["supporting_weight"] = round(supporting_weight, 2)
    clarity["counter_weight"] = round(counter_weight, 2)
    return supporting[:4], counter[:4], clarity


def _analyst_note(
    opening: str,
    context: dict[str, Any],
    decision: dict[str, Any],
    scenario: dict[str, list[str]],
    reconciliation: str = "",
) -> str:
    semantic = context.get("semantic", {})
    trend = semantic.get("trend_quality", {}).get("summary", "Trend kalitesi hesaplanamadı.")
    momentum = semantic.get("momentum_character", {}).get("summary", "Momentum karakteri hesaplanamadı.")
    price_action = semantic.get("price_action", {}).get("summary", "Fiyat davranışı hesaplanamadı.")
    participation = semantic.get("participation", {}).get("summary", "Katılım hesaplanamadı.")
    _, _, rs = _rs_text(decision)
    location = _location_text(context)
    divergences = semantic.get("momentum_character", {}).get("active_divergences", [])
    divergence_text = ""
    if divergences:
        details = "; ".join(
            f"{item.get('indicator', 'Osilatör')} {item.get('state', 'uyumsuzluk')} ({item.get('quality', '—')} kalite; teyit {item.get('event_age', '—')} bar önce, pivotu 5 bar öncesinde)"
            for item in divergences
        )
        divergence_text = f" Aktif uyumsuzluklar: {details}; bunlar erken kanıttır ve yapı/seviye teyidi gerektirir."
    strengthen_first = scenario["strengthen"][0].rstrip(". ")
    weaken_first = scenario["weaken"][0].rstrip(". ")
    if str(context.get("setup_context", {}).get("setup", {}).get("bias", "")) == "iki yönlü":
        closing = f"Yönü netleştirecek ilk eşik: {strengthen_first}. Kurulumu geçersiz kılacak gelişme: {weaken_first}."
    else:
        closing = f"Mevcut okumayı teyit edecek ilk koşul: {strengthen_first}. Okumayı geçersizleştirecek ilk koşul: {weaken_first}."
    setup_context = context.get("setup_context", {})
    setup = setup_context.get("setup", {})
    duration = setup_context.get("duration", {})
    participation_reading = setup_context.get("participation_reading", {})
    if participation_reading.get("meaning"):
        participation = participation_reading["meaning"]
    setup_paragraph = ""
    if setup:
        reasons = "; ".join(setup.get("reasons", [])[:3])
        setup_paragraph = (
            f"Kurulum: {setup['name']} (eğilim: {setup['bias']}). {setup['description']}"
            + (f" Bu sınıflamanın dayanağı: {reasons}." if reasons else "")
        )
    duration_paragraph = ""
    if duration.get("summary") and duration["summary"] != "Belirgin bir süre birikimi yok":
        duration_paragraph = f"Süre bağlamı: {duration['summary']}."
    paragraphs = [
        f"{opening} {setup_paragraph}".strip(),
        f"{trend} {momentum}{divergence_text}".strip(),
        f"{price_action} {participation} {duration_paragraph}".strip(),
        f"{location} {rs}".strip(),
        closing,
    ]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)


def _short_history_note(context: dict[str, Any]) -> str:
    """Hesaplanamayan periyotları adıyla bildirir; ikame yapılmadığını belirtir."""
    missing = ", ".join(str(period) for period in context.get("missing_periods", [])) or "bazı"
    return (
        f"Sembolün geçmişi kısa ({context.get('bar_count', '—')} bar); {missing} periyotluk "
        "ortalamalar hesaplanamadı ve başka periyotlarla ikame edilmedi."
    )


def _indicator_confirmation(data: pd.DataFrame) -> dict[str, str]:
    """Gösterge ailelerini sade cümleye çevirir; ayrı oy veya puan üretmez."""
    row = data.iloc[-1]
    previous = data.iloc[-2]
    momentum: list[str] = []
    flow: list[str] = []

    rsi_value = _number(row.get("RSI"))
    momentum.append(
        f"RSI {rsi_value:.1f} ile " + ("güçlü bölgede" if rsi_value >= 50 else "zayıf bölgede")
    )
    hist = _number(row.get("MACD_HIST"))
    prev_hist = _number(previous.get("MACD_HIST"))
    momentum.append(
        "MACD yükseliş ivmesi " + ("artıyor" if hist > prev_hist else "azalıyor")
        if hist >= 0
        else "MACD düşüş baskısı " + ("azalıyor" if hist > prev_hist else "artıyor")
    )
    momentum.append(
        "SMI sinyalinin üzerinde" if _number(row.get("SMI")) > _number(row.get("SMI_EMA"))
        else "SMI sinyalinin altında"
    )
    momentum.append(
        "Stokastik RSI kısa vadede yukarı dönük"
        if _number(row.get("STOCH_K")) > _number(row.get("STOCH_D"))
        else "Stokastik RSI kısa vadede aşağı dönük"
    )
    momentum.append(
        "Fisher tetik çizgisinin üzerinde"
        if _number(row.get("FISHER")) > _number(row.get("FISHER_TRIGGER"))
        else "Fisher tetik çizgisinin altında"
    )
    momentum.append(
        "10 barlık momentum pozitif"
        if _number(row.get("MOMENTUM")) > 0
        else "10 barlık momentum negatif"
    )

    flow.append(
        "CMF para akışı pozitif" if _number(row.get("CMF")) > 0 else "CMF para akışı negatif"
    )
    flow.append(
        "OBV kendi SMA14 çizgisinin üzerinde"
        if _number(row.get("OBV")) > _number(row.get("OBV_SMA"))
        else "OBV kendi SMA14 çizgisinin altında"
    )
    return {
        "state": "Momentum ve para akışı birlikte okunur",
        "summary": "; ".join(momentum) + ". Para akışı: " + "; ".join(flow) + ".",
        "method": "Aynı ailedeki göstergeler bağımsız oy gibi toplanmaz; yön, ivme ve para akışı teyitleri olarak açıklanır.",
    }


def build_technical_commentary(
    data: pd.DataFrame,
    context: dict[str, Any],
    decision: dict[str, Any],
    bar_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    semantic = context.get("semantic", {})
    direction, direction_tone = _direction(context)
    regime = str(context.get("regime", {}).get("state", "Bilinmeyen rejim"))
    adx = _number(context.get("regime", {}).get("adx"))
    adx_delta = _number(context.get("regime", {}).get("adx_delta"), 0.0)
    stance, tone, opening = _regime_opening(regime, direction, adx, adx_delta)
    levels = _technical_levels(context, direction_tone)
    scenario = _scenario_map(context, decision, direction_tone, levels)
    supporting, counter, clarity = _evidence_and_clarity(context, decision, direction_tone, bar_state)
    changes = _changes(data, context)
    indicator_confirmation = _indicator_confirmation(data)
    reconciliation = reconcile(context.get("setup_context", {}).get("setup", {"name": direction}), supporting, counter)
    analyst_note = _analyst_note(opening, context, decision, scenario, reconciliation)
    rs_state, rs_tone, rs_meaning = _rs_text(decision)
    setup_context = context.get("setup_context", {})
    setup = setup_context.get("setup", {})
    state_map = [
        ["Kurulum", setup.get("name", "—"), f"Eğilim: {setup.get('bias', '—')}", f"{setup.get('description', '—')} {setup_context.get('duration', {}).get('summary', '')}".strip(), setup.get("tone", "warning")],
        ["Rejim", regime, f"ADX Δ {adx_delta:+.2f}", opening, context.get("regime", {}).get("tone", "warning")],
        ["Yapı / trend", f"{context.get('structure', {}).get('state', '—')} | {semantic.get('trend_quality', {}).get('state', '—')}", semantic.get("trend_quality", {}).get("spread_state", "—"), semantic.get("trend_quality", {}).get("summary", "—"), context.get("structure", {}).get("tone", "neutral")],
        ["Momentum", semantic.get("momentum_character", {}).get("state", "—"), semantic.get("momentum_character", {}).get("macd", {}).get("histogram_character", "—"), semantic.get("momentum_character", {}).get("summary", "—"), semantic.get("momentum_character", {}).get("tone", "warning")],
        ["Gösterge teyitleri", indicator_confirmation["state"], "Aynı aile tek kanıt", indicator_confirmation["summary"], "neutral"],
        ["Katılım", setup_context.get("participation_reading", {}).get("state", semantic.get("participation", {}).get("state", "—")), f"RVOL {semantic.get('participation', {}).get('rvol_1', math.nan):.2f}x", setup_context.get("participation_reading", {}).get("meaning", semantic.get("participation", {}).get("summary", "—")), setup_context.get("participation_reading", {}).get("tone", "warning")],
        ["Konum", context.get("profile", {}).get("position", "—"), context.get("profile", {}).get("poc_migration", "—"), _location_text(context), context.get("profile", {}).get("tone", "neutral")],
        ["Göreceli güç", rs_state, f"Eğim5 %{_number(decision.get('relative_strength', {}).get('ratio_slope_5_pct')):+.2f}", rs_meaning, rs_tone],
        ["Fiyat davranışı", semantic.get("price_action", {}).get("state", "—"), ", ".join(semantic.get("price_action", {}).get("patterns", [])) or "Yeni formasyon yok", semantic.get("price_action", {}).get("summary", "—"), semantic.get("price_action", {}).get("tone", "neutral")],
    ]
    plain = build_plain_summary(
        str(context.get("symbol", "—")),
        _number(data["Close"].iloc[-1]),
        _number(context.get("change_pct"), 0.0),
        setup_context,
        scenario,
        clarity,
        bar_state,
        bool(context.get("short_history")),
    )
    headline = f"{stance}. {opening} Teknik okuma netliği: {clarity['state'].casefold()}."
    telegram_detail = "\n".join(
        [
            "🗣️ Sade Özet",
            plain["text"],
            "",
            "🧭 Analist Notu",
            analyst_note,
            "",
            "📐 Gösterge Teyitleri",
            indicator_confirmation["summary"],
            "",
            "⚖️ Neden bu okuma?",
            reconciliation,
            "",
            "🔄 Dünden Bugüne",
            *[f"• {item}" for item in changes],
            "",
            f"✅ {scenario['labels']['strengthen']}",
            *[f"• {item}" for item in scenario["strengthen"]],
            "",
            f"⚠️ {scenario['labels']['weaken']}",
            *[f"• {item}" for item in scenario["weaken"]],
            "",
            f"↔️ {scenario['labels']['neutral']}",
            *[f"• {item}" for item in scenario["neutral"]],
            "",
            f"Okuma netliği: {clarity['state']} — {clarity['reason']}",
            "Teknik durum yorumudur; yatırım tavsiyesi veya otomatik AL/SAT sinyali değildir.",
        ]
    )
    return {
        "version": "2.1",
        "setup": setup,
        "duration": setup_context.get("duration", {}),
        "reconciliation": reconciliation,
        "plain_summary": plain,
        "stance": stance,
        "tone": tone,
        "headline": headline,
        "analyst_note": analyst_note,
        "indicator_confirmation": indicator_confirmation,
        "direction": direction,
        "regime": regime,
        "changes": changes,
        "state_comparison": context.get("state_comparison", {}),
        "supporting_evidence": supporting,
        "counter_evidence": counter,
        "evidence": [f"{item['family']}: {item['state']}" for item in supporting],
        "conflicts": [f"{item['family']}: {item['state']}" for item in counter],
        "clarity": clarity,
        "levels": levels,
        "scenario_map": scenario,
        "state_map": state_map,
        "visual_rows": [[item[0], item[1], item[3], item[4]] for item in state_map],
        "watch": scenario["strengthen"] + scenario["weaken"],
        "telegram_summary": headline,
        "telegram_detail": telegram_detail,
        "framework": ["Regime", "Direction", "Location", "Setup", "Trigger", "Confirmation", "Risk", "Exit"],
        "method": "Deterministik, rejim-duyarlı teknik yorum; bağımsız kanıt aileleri kullanır ve birleşik AL/SAT puanı üretmez.",
        "limitations": [
            *(
                [
                    "VERİ UYARISI: " + str(context.get("corporate_action", {}).get("reason", ""))
                    + " Bu seride göstergeler güvenilir değildir."
                ]
                if context.get("corporate_action", {}).get("suspect")
                else []
            ),
            *(
                [_short_history_note(context)]
                if context.get("short_history")
                else []
            ),
            "Yorum yalnız OHLCV ve türetilmiş teknik bağlama dayanır; haber/KAP/temel veri içermez.",
            "Volume Profile ve delta alanları yaklaşık OHLCV proxy'dir; gerçek footprint değildir.",
            "Göreceli güç fon akışı değildir; RVOL kurumsal katılımı kanıtlamaz.",
            "CANLI mum kapanışa kadar değişebilir; uyumsuzluk ve swingler sağ pivot barları tamamlanınca teyit edilir.",
        ],
    }
