from __future__ import annotations

from typing import Any, Iterable

from .models import Evidence, EvidenceDirection, LevelLifecycle, TechnicalLevel, WaveHypothesis


def _nearest(levels: Iterable[TechnicalLevel], price: float, side: str) -> TechnicalLevel | None:
    eligible = [
        item
        for item in levels
        if item.lifecycle_state not in {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}
        and ((side == "ABOVE" and item.value > price) or (side == "BELOW" and item.value < price))
    ]
    return min(eligible, key=lambda item: abs(item.value - price), default=None)


def _structure_sentence(structure: dict[str, Any]) -> str:
    state = str(structure.get("state", "INSUFFICIENT"))
    if state == "HH/HL":
        return "Teyitli swing yapısı yükseliş yönünde (HH/HL)."
    if state == "LH/LL":
        return "Teyitli swing yapısı düşüş yönünde (LH/LL)."
    if state == "INSUFFICIENT":
        return "Yapıyı sınıflamak için yeterli teyitli pivot yok."
    return f"Teyitli swing yapısı geçiş/karışık durumda ({state})."


def _wave_sentence(waves: list[WaveHypothesis]) -> str:
    if not waves:
        return "Hard-rule geçen yeterli Elliott hipotezi oluşmadı."
    primary = waves[0]
    text = (
        f"Birincil Elliott hipotezi {primary.pattern_type}, {primary.direction} yönünde; "
        f"aktif durum {primary.active_wave}, güven {primary.confidence:.2f}."
    )
    if len(waves) > 1:
        alternate = waves[1]
        text += f" Alternatif sayım {alternate.pattern_type}/{alternate.direction}, güven {alternate.confidence:.2f}."
    return text


def _evidence_sentence(summary: dict[str, Any]) -> str:
    bull = float(summary.get("bullish", 0.0))
    bear = float(summary.get("bearish", 0.0))
    uncertainty = float(summary.get("uncertainty", 0.0))
    clarity = float(summary.get("clarity", 0.0))
    if bull > bear * 1.25:
        direction = "Yönlü kanıt dengesi yukarı tarafta."
    elif bear > bull * 1.25:
        direction = "Yönlü kanıt dengesi aşağı tarafta."
    else:
        direction = "Yukarı ve aşağı yönlü kanıtlar birbirine yakın."
    return f"{direction} Belirsizlik skoru {uncertainty:.2f}; netlik {clarity:.2f}."


def _context_sentence(regime: dict[str, Any], relative_strength: dict[str, Any], multi_timeframe: dict[str, Any]) -> str:
    parts = [f"Rejim: {regime.get('state', '—')}." ]
    if relative_strength.get("available"):
        parts.append(
            f"Göreceli güç: {relative_strength.get('state', 'MIXED')} ({relative_strength.get('benchmark', 'benchmark')})."
        )
    else:
        parts.append("Göreceli güç: benchmark verisi yok.")
    if multi_timeframe.get("available"):
        parts.append(f"Çoklu zaman dilimi: {multi_timeframe.get('state', '—')}.")
    else:
        parts.append("Çoklu zaman dilimi: ek interval state'i yok.")
    return " ".join(parts)


def _changed_roles(levels: Iterable[TechnicalLevel]) -> list[str]:
    result: list[str] = []
    for level in levels:
        if level.lifecycle_state == LevelLifecycle.BROKEN_DOWN and level.role == "FORMER_SUPPORT_RECLAIM":
            result.append(f"{level.value:.2f} eski desteği aşağı kırılmış; artık yeniden kazanım/direnç referansıdır.")
        elif level.lifecycle_state == LevelLifecycle.REJECTED and "SUPPORT" in level.role:
            result.append(f"{level.value:.2f} çevresinde eski destek geri kazanılamamış/reddedilmiş durumda.")
        elif level.lifecycle_state == LevelLifecycle.BROKEN_UP and level.role == "FORMER_RESISTANCE_RETEST":
            result.append(f"{level.value:.2f} eski direnci yukarı kırılmış; artık geri test/destek referansıdır.")
        elif level.lifecycle_state == LevelLifecycle.TESTED and "RETEST_HELD" in level.role:
            result.append(f"{level.value:.2f} kırılım sonrası geri testte korunmuş durumda.")
        elif level.lifecycle_state == LevelLifecycle.RECLAIMED:
            result.append(f"{level.value:.2f} seviyesi kırılım sonrası yeniden kazanılmış durumda.")
    return result[-5:]


def build_interpretation(
    *,
    price: float,
    structure: dict[str, Any],
    waves: list[WaveHypothesis],
    levels: list[TechnicalLevel],
    scenarios: list[dict[str, Any]],
    evidence: list[Evidence],
    evidence_summary: dict[str, Any],
    critical_data_quality: bool = False,
    regime: dict[str, Any] | None = None,
    relative_strength: dict[str, Any] | None = None,
    multi_timeframe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical state'ten yeni teknik hesap yapmadan analist görünümü üretir."""
    if critical_data_quality:
        return {
            "available": False,
            "headline": "Teknik yorum veri kalitesi nedeniyle durduruldu.",
            "current_state": "Kritik veri sürekliliği/kalitesi sorunu çözülmeden yön ve seviye yorumu üretilmez.",
            "location": None,
            "wave": None,
            "context": None,
            "evidence": None,
            "up_scenario": [],
            "down_scenario": [],
            "role_changes": [],
        }

    regime = dict(regime or {})
    relative_strength = dict(relative_strength or {})
    multi_timeframe = dict(multi_timeframe or {})
    nearest_above = _nearest(levels, price, "ABOVE")
    nearest_below = _nearest(levels, price, "BELOW")
    location_parts = [f"Fiyat {price:.2f}."]
    if nearest_below:
        location_parts.append(f"En yakın alt referans {nearest_below.value:.2f} ({nearest_below.role}, {nearest_below.level_class.value}).")
    if nearest_above:
        location_parts.append(f"En yakın üst referans {nearest_above.value:.2f} ({nearest_above.role}, {nearest_above.level_class.value}).")

    up = [item for item in scenarios if str(item.get("side")) == "UP"]
    down = [item for item in scenarios if str(item.get("side")) == "DOWN"]
    bias = float(evidence_summary.get("directional_bias", 0.0))
    clarity = float(evidence_summary.get("clarity", 0.0))
    if clarity < 0.35:
        headline = "Yön teyidi zayıf; yapı ve senaryo seviyeleri izlenmeli."
    elif bias > 0.25:
        headline = "Teknik kanıt dengesi yukarı eğilimli; teyit seviyeleri belirleyici."
    elif bias < -0.25:
        headline = "Teknik kanıt dengesi aşağı eğilimli; toparlanma için geri kazanım seviyeleri önemli."
    else:
        headline = "Teknik kanıt dengesi karışık; fiyatın yakın yapısal seviyelerden çıkışı bekleniyor."

    return {
        "available": True,
        "headline": headline,
        "current_state": _structure_sentence(structure),
        "location": " ".join(location_parts),
        "wave": _wave_sentence(waves),
        "context": _context_sentence(regime, relative_strength, multi_timeframe),
        "evidence": _evidence_sentence(evidence_summary),
        "up_scenario": [item.get("confirmation_rule") for item in up],
        "down_scenario": [item.get("confirmation_rule") for item in down],
        "role_changes": _changed_roles(levels),
        "evidence_counts": {
            direction.value: sum(1 for item in evidence if item.direction == direction)
            for direction in EvidenceDirection
        },
    }
