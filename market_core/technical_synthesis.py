from __future__ import annotations

from typing import Any


def _section_state(features: dict[str, Any], name: str) -> str:
    sections = features.get("sections") if features.get("available") else {}
    return str((sections or {}).get(name, {}).get("state") or "INSUFFICIENT")


def _short_ma_state(features: dict[str, Any]) -> str:
    sections = features.get("sections") if features.get("available") else {}
    trend = (sections or {}).get("trend_and_averages", {}) or {}
    return str((trend.get("short_ma") or {}).get("state") or "INSUFFICIENT")


def _live_scanner_sides(scanner_evidence: list[dict[str, Any]]) -> set[str]:
    live_states = {"NEW", "ACTIVE", "CONFIRMED"}
    return {
        str(item.get("side") or "NEUTRAL")
        for item in scanner_evidence
        if str(item.get("state") or "").upper() in live_states
    }


def _nearest_ma_side(ma_levels: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    candidates = [
        item
        for item in ma_levels
        if str(item.get("side") or "") == side
        and item.get("distance_atr") is not None
    ]
    if not candidates:
        return None
    try:
        return min(candidates, key=lambda item: abs(float(item.get("distance_atr"))))
    except (TypeError, ValueError):
        return None


def build_technical_synthesis(
    *,
    structure: dict[str, Any],
    technical_features: dict[str, Any],
    scanner_evidence: list[dict[str, Any]],
    ma_level_evidence: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
) -> dict[str, Any]:
    """Explain agreements and conflicts without converting them into a trade command."""
    structure_bias = str(structure.get("bias") or "TRANSITION")
    price_position = str(structure.get("price_position") or "UNAVAILABLE")
    short_ma = _short_ma_state(technical_features)
    trend_state = _section_state(technical_features, "trend_and_averages")
    momentum = _section_state(technical_features, "momentum")
    participation = _section_state(technical_features, "participation")
    live_scanners = _live_scanner_sides(scanner_evidence)
    near_support = _nearest_ma_side(ma_level_evidence, "SUPPORT")
    near_resistance = _nearest_ma_side(ma_level_evidence, "RESISTANCE")

    positives: list[str] = []
    risks: list[str] = []
    conflicts: list[str] = []

    if structure_bias == "BULLISH":
        positives.append("Teyitli swing yapısı yükseliş yönünde.")
    elif structure_bias == "BEARISH":
        risks.append("Teyitli swing yapısı düşüş yönünde.")

    if short_ma == "BULLISH_ALIGNMENT":
        positives.append("EMA5/8/13 kısa vadede pozitif hizalanmış.")
    elif short_ma == "BEARISH_ALIGNMENT":
        risks.append("EMA5/8/13 kısa vadede negatif hizalanmış.")

    if momentum == "POSITIVE":
        positives.append("Momentum ailesi ağırlıklı olarak pozitif.")
    elif momentum == "NEGATIVE":
        risks.append("Momentum ailesi ağırlıklı olarak negatif.")

    if participation == "STRONG_PARTICIPATION":
        positives.append("Hareket güçlü göreceli hacim katılımı görüyor.")
    elif participation == "LOW_PARTICIPATION":
        risks.append("Katılım zayıf; yönlü sinyallerin teyidi sınırlı.")

    if "BUY" in live_scanners:
        positives.append("Taramabot'ta güncel AL yönlü tarama eşleşmesi var.")
    if "SELL" in live_scanners:
        risks.append("Taramabot'ta güncel SAT yönlü tarama eşleşmesi var.")

    if short_ma.startswith("BULLISH") and structure_bias == "BEARISH":
        conflicts.append(
            "Kısa ortalamalar toparlanırken ana swing yapısı hâlâ düşüş yönünde; bu görünüm trend dönüşü değil erken toparlanma olarak okunmalı."
        )
    if short_ma.startswith("BEARISH") and structure_bias == "BULLISH":
        conflicts.append(
            "Kısa ortalamalar zayıflarken ana swing yapısı yükseliş yönünü koruyor; kısa vadeli düzeltme ile ana yapı ayrışıyor."
        )
    if momentum == "POSITIVE" and structure_bias == "BEARISH":
        conflicts.append("Pozitif momentum, düşüş yönlü yapıyı tek başına tersine çevirmiş sayılmaz.")
    if momentum == "NEGATIVE" and structure_bias == "BULLISH":
        conflicts.append("Negatif momentum, yükseliş yönlü ana yapının tek başına bozulduğu anlamına gelmez.")
    if "BUY" in live_scanners and structure_bias == "BEARISH":
        conflicts.append("AL taraması mevcut olsa da yapı teyidi eksik; tarama erken evreli sinyal olarak tutulur.")
    if "SELL" in live_scanners and structure_bias == "BULLISH":
        conflicts.append("SAT taraması mevcut olsa da ana yükseliş yapısı henüz bozulmuş değil.")
    if "BUY" in live_scanners and "SELL" in live_scanners:
        conflicts.append("Farklı taramalar zıt yönlü eşleşiyor; tek yönlü sonuç üretmek için kanıtlar yeterince uyumlu değil.")

    if near_resistance is not None:
        try:
            distance = abs(float(near_resistance.get("distance_atr")))
        except (TypeError, ValueError):
            distance = 99.0
        if distance <= 1.0 and (short_ma.startswith("BULLISH") or momentum == "POSITIVE"):
            conflicts.append("Olumlu kısa vadeli görünümün hemen üzerinde gözlemsel MA direnci bulunuyor; kırılım teyidi beklenmeli.")

    if near_support is not None:
        try:
            distance = abs(float(near_support.get("distance_atr")))
        except (TypeError, ValueError):
            distance = 99.0
        if distance <= 1.0 and (short_ma.startswith("BEARISH") or momentum == "NEGATIVE"):
            conflicts.append("Zayıf kısa vadeli görünümün hemen altında gözlemsel MA desteği bulunuyor; destek kırılmadan aşağı yön teyidi sınırlı.")

    if price_position == "BELOW_STRUCTURE":
        risks.append("Fiyat son teyitli swing yapısının alt tarafında.")
    elif price_position == "ABOVE_STRUCTURE":
        positives.append("Fiyat son teyitli swing yapısının üst tarafında.")

    directional_bias = float(evidence_summary.get("directional_bias") or 0.0)
    clarity = float(evidence_summary.get("clarity") or 0.0)

    if clarity < 0.35:
        state = "HIGH_UNCERTAINTY"
        headline = "Teknik görünümde yön teyidi zayıf; çelişkiler ve seviye reaksiyonları izlenmeli."
    elif conflicts:
        if structure_bias == "BEARISH" and (short_ma.startswith("BULLISH") or momentum == "POSITIVE"):
            state = "EARLY_RECOVERY"
            headline = "Kısa vadeli toparlanma belirtileri var, ancak ana yapı dönüşü henüz teyit edilmedi."
        elif structure_bias == "BULLISH" and (short_ma.startswith("BEARISH") or momentum == "NEGATIVE"):
            state = "BULLISH_STRUCTURE_WITH_PULLBACK"
            headline = "Ana yükseliş yapısı korunurken kısa vadeli göstergelerde zayıflama var."
        else:
            state = "MIXED"
            headline = "Teknik kanıtlar tam uyumlu değil; çelişkiler kullanıcıdan saklanmadan izlenmeli."
    elif directional_bias > 0.25 and structure_bias == "BULLISH":
        state = "BULLISH_ALIGNMENT"
        headline = "Yapı ve teknik kanıtlar ağırlıklı olarak aynı yönde pozitif uyum gösteriyor."
    elif directional_bias < -0.25 and structure_bias == "BEARISH":
        state = "BEARISH_ALIGNMENT"
        headline = "Yapı ve teknik kanıtlar ağırlıklı olarak aynı yönde negatif uyum gösteriyor."
    elif trend_state == "MIXED" or structure_bias == "TRANSITION":
        state = "MIXED"
        headline = "Teknik görünüm geçiş/karışık bölgede; seviye teyidi belirleyici."
    else:
        state = "NO_CLEAR_EDGE"
        headline = "Teknik görünüm tek yönlü güçlü bir üstünlük göstermiyor."

    return {
        "state": state,
        "headline": headline,
        "positives": positives[:6],
        "risks": risks[:6],
        "conflicts": conflicts[:6],
        "live_scanner_sides": sorted(live_scanners),
        "historical_scanner_count": sum(
            1 for item in scanner_evidence if str(item.get("state") or "").upper() == "HISTORICAL"
        ),
        "data_note": (
            "Geçmiş taramabot kayıtları güncel eşleşme sayılmaz; yalnız NEW/ACTIVE/CONFIRMED kayıtlar senteze yönlü bağlam verir."
        ),
    }
