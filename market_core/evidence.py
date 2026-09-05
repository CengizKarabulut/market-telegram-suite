from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Iterable

from .models import Evidence, EvidenceDirection, LevelClass, LevelLifecycle, TechnicalLevel, WaveHypothesis


def _clamp(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def structure_evidence(structure: dict[str, Any]) -> list[Evidence]:
    state = str(structure.get("state", "INSUFFICIENT"))
    bias = str(structure.get("bias", "TRANSITION"))
    if state == "INSUFFICIENT":
        return [
            Evidence(
                family="structure",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Yetersiz teyitli pivot",
                strength=0.35,
                confidence=0.9,
                independent_group="price_structure",
                reason="HH/HL/LH/LL sınıflaması için yeterli teyitli swing bulunmuyor.",
            )
        ]
    direction = (
        EvidenceDirection.BULLISH
        if bias == "BULLISH"
        else EvidenceDirection.BEARISH
        if bias == "BEARISH"
        else EvidenceDirection.NEUTRAL
    )
    result = [
        Evidence(
            family="structure",
            direction=direction,
            state=state,
            strength=0.85 if direction != EvidenceDirection.NEUTRAL else 0.45,
            confidence=0.9,
            independent_group="price_structure",
            reason=f"Teyitli swing dizisi {state} yapısında.",
        )
    ]
    events = structure.get("events", [])
    if events:
        event = events[-1]
        kind = str(getattr(event, "kind", ""))
        event_direction = EvidenceDirection.BULLISH if kind.endswith("UP") else EvidenceDirection.BEARISH
        is_choch = kind.startswith("CHOCH")
        result.append(
            Evidence(
                family="structure_event",
                direction=event_direction,
                state=kind,
                strength=0.82 if is_choch else 0.72,
                confidence=0.9,
                independent_group="structure_break",
                reason=(
                    "Son teyitli olay önceki yapının tersine CHoCH üretti."
                    if is_choch
                    else "Son teyitli olay yapı yönünde BOS üretti."
                ),
                metadata={"level": float(getattr(event, "level", 0.0)), "trigger_index": int(getattr(event, "trigger_index", -1))},
            )
        )
    return result


def wave_evidence(hypotheses: list[WaveHypothesis]) -> list[Evidence]:
    if not hypotheses:
        return [
            Evidence(
                family="wave",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Geçerli Elliott hipotezi yok",
                strength=0.25,
                confidence=0.8,
                independent_group="elliott",
                reason="Hard-rule geçen yeterli impulse/ABC adayı oluşmadı.",
            )
        ]
    primary = hypotheses[0]
    completed = "COMPLETE" in str(primary.active_wave).upper()
    direction = (
        EvidenceDirection.NEUTRAL
        if completed
        else EvidenceDirection.BULLISH
        if primary.direction == "UP"
        else EvidenceDirection.BEARISH
    )
    reason = (
        f"Primary Elliott hipotezi {primary.direction} yönünde tamamlanmış yapı; yönlü oy değil bağlam olarak tutulur."
        if completed
        else f"Primary Elliott hipotezi {primary.direction} yönünde; güven {primary.confidence:.2f}."
    )
    result = [
        Evidence(
            family="wave",
            direction=direction,
            state=f"{primary.pattern_type} / {primary.active_wave}",
            strength=_clamp(primary.confidence),
            confidence=_clamp(primary.confidence),
            independent_group="elliott",
            reason=reason,
            metadata={"wave_id": primary.id, "rank": primary.alternate_rank},
        )
    ]
    if len(hypotheses) > 1:
        alternate = hypotheses[1]
        alternate_completed = "COMPLETE" in str(alternate.active_wave).upper()
        if (
            not completed
            and not alternate_completed
            and alternate.direction != primary.direction
            and alternate.confidence >= primary.confidence - 0.15
        ):
            result.append(
                Evidence(
                    family="wave_alternate",
                    direction=EvidenceDirection.UNCERTAINTY,
                    state="Yakın güçlü alternatif sayım",
                    strength=_clamp(alternate.confidence),
                    confidence=_clamp(alternate.confidence),
                    independent_group="elliott_uncertainty",
                    reason="Primary sayımın ters yönünde benzer güvene sahip alternatif Elliott hipotezi var.",
                    metadata={"wave_id": alternate.id},
                )
            )
    return result


def _location_direction(level: TechnicalLevel) -> EvidenceDirection:
    """Fiyatin bir seviyeye gore konumu tek basina yonlu oy degildir.

    Reclaim/rejection gibi olaylar structure/lifecycle kanitinda degerlendirilir.
    Location ailesinin gorevi yalnizca fiyatin nerede oldugunu anlatmaktir;
    aksi halde ayni yapisal olay iki kez bullish/bearish oy olarak sayilabilir.
    """
    _ = level
    return EvidenceDirection.NEUTRAL


def level_evidence(levels: Iterable[TechnicalLevel], price: float) -> list[Evidence]:
    nearby = [
        level
        for level in levels
        if level.level_class == LevelClass.NEAR_TERM
        and level.lifecycle_state not in {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}
    ]
    if not nearby:
        return [
            Evidence(
                family="location",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Yakın aktif seviye yok",
                strength=0.3,
                confidence=0.8,
                independent_group="location",
                reason="Fiyatın 1.5 ATR çevresinde yeterince güçlü aktif teknik seviye oluşmadı.",
            )
        ]
    below = [item for item in nearby if item.value < price]
    above = [item for item in nearby if item.value > price]
    result: list[Evidence] = []
    if below:
        support = min(below, key=lambda item: abs(item.value - price))
        result.append(
            Evidence(
                family="location_support",
                direction=_location_direction(support),
                state=support.role,
                strength=_clamp(support.priority),
                confidence=_clamp(support.confidence),
                independent_group="location_support",
                reason=f"En yakın aktif alt referans {support.value:.2f}; rolü {support.role}. Konum tek başına yön oyu değildir.",
                metadata={"level": support.value, "source": support.source},
            )
        )
    if above:
        resistance = min(above, key=lambda item: abs(item.value - price))
        result.append(
            Evidence(
                family="location_resistance",
                direction=_location_direction(resistance),
                state=resistance.role,
                strength=_clamp(resistance.priority),
                confidence=_clamp(resistance.confidence),
                independent_group="location_resistance",
                reason=f"En yakın aktif üst referans {resistance.value:.2f}; rolü {resistance.role}. Konum tek başına yön oyu değildir.",
                metadata={"level": resistance.value, "source": resistance.source},
            )
        )
    return result


def indicator_evidence(indicators: dict[str, Any]) -> list[Evidence]:
    result: list[Evidence] = []
    momentum_votes: list[float] = []
    for key in ("RSI", "MACD_HIST", "SMI"):
        value = _number(indicators.get(key))
        if value is None:
            continue
        if key == "RSI":
            momentum_votes.append(1.0 if value > 55 else -1.0 if value < 45 else 0.0)
        else:
            momentum_votes.append(1.0 if value > 0 else -1.0 if value < 0 else 0.0)
    if momentum_votes:
        avg = sum(momentum_votes) / len(momentum_votes)
        direction = EvidenceDirection.BULLISH if avg > 0.25 else EvidenceDirection.BEARISH if avg < -0.25 else EvidenceDirection.NEUTRAL
        result.append(
            Evidence(
                family="momentum",
                direction=direction,
                state="Momentum aile özeti",
                strength=_clamp(abs(avg)),
                confidence=min(0.55 + len(momentum_votes) * 0.12, 0.9),
                independent_group="momentum",
                reason="RSI/MACD histogram/SMI aynı momentum ailesinde tek kanıta birleştirildi.",
            )
        )
    else:
        result.append(
            Evidence(
                family="momentum",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Momentum verisi yok",
                strength=0.25,
                confidence=0.85,
                independent_group="momentum",
                reason="Momentum göstergelerinin canonical değerleri sağlanmadı.",
            )
        )

    rvol = _number(indicators.get("RVOL"))
    if rvol is None:
        result.append(
            Evidence(
                family="participation",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Katılım verisi yok",
                strength=0.25,
                confidence=0.8,
                independent_group="participation",
                reason="RVOL bulunmadığı için hareketin katılım teyidi ölçülemiyor.",
            )
        )
    elif rvol < 0.8:
        result.append(
            Evidence(
                family="participation",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Düşük katılım",
                strength=_clamp((0.8 - rvol) / 0.8),
                confidence=0.9,
                independent_group="participation",
                reason=f"RVOL {rvol:.2f}x; düşük katılım yönlü oy değil, güven azaltıcıdır.",
            )
        )
    else:
        result.append(
            Evidence(
                family="participation",
                direction=EvidenceDirection.NEUTRAL,
                state="Katılım yeterli",
                strength=_clamp(min((rvol - 0.8) / 1.2, 1.0)),
                confidence=0.85,
                independent_group="participation",
                reason=f"RVOL {rvol:.2f}x; katılım mevcut ancak yönü tek başına belirlemez.",
            )
        )
    return result


def build_evidence(
    *,
    structure: dict[str, Any],
    hypotheses: list[WaveHypothesis],
    levels: Iterable[TechnicalLevel],
    price: float,
    indicators: dict[str, Any] | None = None,
) -> tuple[list[Evidence], dict[str, Any]]:
    result: list[Evidence] = []
    result.extend(structure_evidence(structure))
    result.extend(wave_evidence(hypotheses))
    result.extend(level_evidence(levels, price))
    result.extend(indicator_evidence(indicators or {}))
    return result, summarize_evidence(result)


def summarize_evidence(evidence: Iterable[Evidence]) -> dict[str, Any]:
    """Bağımsız grupları tek oy kabul ederek yönlü ve belirsizlik skorlarını ayırır."""
    groups: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence:
        groups[item.independent_group or item.family].append(item)
    contributions: dict[str, float] = {
        "bullish": 0.0,
        "bearish": 0.0,
        "neutral": 0.0,
        "uncertainty": 0.0,
    }
    group_details: list[dict[str, Any]] = []
    for group, items in groups.items():
        representative = max(items, key=lambda item: item.strength * item.confidence * item.freshness)
        weight = _clamp(representative.strength) * _clamp(representative.confidence) * _clamp(representative.freshness)
        key = representative.direction.value.lower()
        contributions[key] += weight
        group_details.append(
            {
                "group": group,
                "direction": representative.direction.value,
                "weight": weight,
                "representative": asdict(representative),
                "member_count": len(items),
            }
        )
    directional = contributions["bullish"] + contributions["bearish"]
    bias = (
        (contributions["bullish"] - contributions["bearish"]) / directional
        if directional > 0
        else 0.0
    )
    total = sum(contributions.values())
    uncertainty_share = contributions["uncertainty"] / total if total > 0 else 1.0
    clarity = max(0.0, 1.0 - uncertainty_share)
    return {
        **contributions,
        "directional_bias": bias,
        "uncertainty_share": uncertainty_share,
        "clarity": clarity,
        "groups": group_details,
    }
