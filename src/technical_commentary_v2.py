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


def _direction(context: dict[str, Any]) -> tuple[str, str]:
    structure = context.get("structure", {}).get("state", "Yetersiz pivot")
    trend = context.get("semantic", {}).get("trend_quality", {})
    if structure == "HH / HL":
        return "Yukarı yönlü yapı", "positive"
    if structure == "LH / LL":
        return "Aşağı yönlü yapı", "negative"
    if trend.get("tone") == "positive":
        return "Ortalamalar yukarı eğilimli", "positive"
    if trend.get("tone") == "negative":
        return "Ortalamalar aşağı eğilimli", "negative"
    return "Yön teyidi karışık", "warning"


def _regime_opening(regime: str, direction: str, adx: float, adx_delta: float) -> tuple[str, str, str]:
    if "sıkışma" in regime.casefold() or "denge" in regime.casefold():
        return (
            "Denge / teyit bekliyor",
            "warning",
            f"Piyasa {regime.casefold()} rejiminde; {direction.casefold()} bulunsa da daralan hareket alanında kesişimlerin bilgi değeri düşebilir. Yeni yön için bant genişlemesi, kapanışla seviye kabulü ve hacim teyidi gerekir.",
        )
    if "yönsüz" in regime.casefold():
        return (
            "Yönsüz volatilite / seçicilik gerekli",
            "warning",
            f"Volatilite genişliyor fakat yönlülük zayıf; ADX {_fmt(adx)}. {direction} tek başına kalıcı kırılım teyidi değildir.",
        )
    if regime.startswith(("Trend", "Yönlü")):
        strength = "güç kazanıyor" if adx_delta > 0 else "güç kaybediyor" if adx_delta < 0 else "yatay"
        tone = "positive" if direction.startswith(("Yukarı", "Ortalamalar yukarı")) else "negative" if direction.startswith(("Aşağı", "Ortalamalar aşağı")) else "warning"
        return (
            f"{direction} / {regime}",
            tone,
            f"{regime}; ADX {_fmt(adx)} ve bir barlık değişimi {adx_delta:+.2f}, yani yönlülük {strength}. {direction}.",
        )
    return (
        "Geçiş / çelişkili bağlam",
        "warning",
        f"{regime}; {direction.casefold()}. Yapı, momentum ve katılım aynı yönde teyit vermeden tek bir göstergeye dayalı okuma zayıf kalır.",
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
    if direction_tone == "positive":
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
    return {"strengthen": strengthen[:3], "weaken": weaken[:3], "neutral": neutral[:3]}


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
    supporting: list[dict[str, str]] = []
    counter: list[dict[str, str]] = []
    for family, state, tone in families:
        item = {"family": family, "state": str(state), "tone": str(tone)}
        if tone == direction_tone:
            supporting.append(item)
        elif tone in {"positive", "negative"} and direction_tone in {"positive", "negative"}:
            counter.append(item)
    if decision.get("multi_timeframe", {}).get("tone") == "warning":
        counter.append({"family": "MTF", "state": "Günlük/haftalık/aylık yönler tam uyumlu değil", "tone": "warning"})
    if bar_state and bar_state.get("is_live"):
        counter.append({"family": "Bar", "state": "Son mum CANLI; kapanışa kadar sınıflamalar değişebilir", "tone": "warning"})
    if len(counter) <= 1 and len(supporting) >= 4:
        clarity = {"state": "Yüksek", "tone": "positive", "reason": "Bağımsız teknik aileler büyük ölçüde aynı yönde."}
    elif len(counter) >= 3:
        clarity = {"state": "Düşük", "tone": "warning", "reason": "Bağımsız teknik aileler belirgin biçimde ayrışıyor."}
    else:
        clarity = {"state": "Orta", "tone": "neutral", "reason": "Ana yön mevcut ancak bazı katmanlar teyidi sınırlıyor."}
    return supporting[:4], counter[:4], clarity


def _analyst_note(
    opening: str,
    context: dict[str, Any],
    decision: dict[str, Any],
    scenario: dict[str, list[str]],
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
            f"{item.get('indicator', 'Osilatör')} {item.get('state', 'uyumsuzluk')} ({item.get('quality', '—')} kalite, {item.get('event_age', '—')} bar)"
            for item in divergences
        )
        divergence_text = f" Aktif uyumsuzluklar: {details}; bunlar erken kanıttır ve yapı/seviye teyidi gerektirir."
    strengthen_first = scenario["strengthen"][0].rstrip(". ")
    weaken_first = scenario["weaken"][0].rstrip(". ")
    closing = f"Mevcut okumayı teyit edecek ilk koşul: {strengthen_first}. Okumayı geçersizleştirecek ilk koşul: {weaken_first}."
    return (
        f"{opening} {trend} {momentum}{divergence_text} {price_action} {participation} "
        f"{location} {rs} {closing}"
    )


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
    analyst_note = _analyst_note(opening, context, decision, scenario)
    rs_state, rs_tone, rs_meaning = _rs_text(decision)
    state_map = [
        ["Rejim", regime, f"ADX Δ {adx_delta:+.2f}", opening, context.get("regime", {}).get("tone", "warning")],
        ["Yapı / trend", direction, semantic.get("trend_quality", {}).get("spread_state", "—"), semantic.get("trend_quality", {}).get("summary", "—"), direction_tone],
        ["Momentum", semantic.get("momentum_character", {}).get("state", "—"), semantic.get("momentum_character", {}).get("macd", {}).get("histogram_character", "—"), semantic.get("momentum_character", {}).get("summary", "—"), semantic.get("momentum_character", {}).get("tone", "warning")],
        ["Katılım", semantic.get("participation", {}).get("state", "—"), f"RVOL {semantic.get('participation', {}).get('rvol_1', math.nan):.2f}x", semantic.get("participation", {}).get("summary", "—"), semantic.get("participation", {}).get("tone", "warning")],
        ["Konum", context.get("profile", {}).get("position", "—"), context.get("profile", {}).get("poc_migration", "—"), _location_text(context), context.get("profile", {}).get("tone", "neutral")],
        ["Göreceli güç", rs_state, f"Eğim5 %{_number(decision.get('relative_strength', {}).get('ratio_slope_5_pct')):+.2f}", rs_meaning, rs_tone],
        ["Fiyat davranışı", semantic.get("price_action", {}).get("state", "—"), ", ".join(semantic.get("price_action", {}).get("patterns", [])) or "Yeni formasyon yok", semantic.get("price_action", {}).get("summary", "—"), semantic.get("price_action", {}).get("tone", "neutral")],
    ]
    headline = f"{stance}. {opening} Teknik okuma netliği: {clarity['state'].casefold()}."
    telegram_detail = "\n".join(
        [
            "🧭 Analist Notu",
            analyst_note,
            "",
            "🔄 Dünden Bugüne",
            *[f"• {item}" for item in changes],
            "",
            "✅ Görünümü güçlendirecek",
            *[f"• {item}" for item in scenario["strengthen"]],
            "",
            "⚠️ Görünümü zayıflatacak",
            *[f"• {item}" for item in scenario["weaken"]],
            "",
            "↔️ Nötr tutacak",
            *[f"• {item}" for item in scenario["neutral"]],
            "",
            f"Okuma netliği: {clarity['state']} — {clarity['reason']}",
            "Teknik durum yorumudur; yatırım tavsiyesi veya otomatik AL/SAT sinyali değildir.",
        ]
    )
    return {
        "version": "2.0",
        "stance": stance,
        "tone": tone,
        "headline": headline,
        "analyst_note": analyst_note,
        "direction": direction,
        "regime": regime,
        "changes": changes,
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
            "Yorum yalnız OHLCV ve türetilmiş teknik bağlama dayanır; haber/KAP/temel veri içermez.",
            "Volume Profile ve delta alanları yaklaşık OHLCV proxy'dir; gerçek footprint değildir.",
            "Göreceli güç fon akışı değildir; RVOL kurumsal katılımı kanıtlamaz.",
            "CANLI mum kapanışa kadar değişebilir; uyumsuzluk ve swingler sağ pivot barları tamamlanınca teyit edilir.",
        ],
    }
