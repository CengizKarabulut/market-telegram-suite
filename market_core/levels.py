from __future__ import annotations

import math
from dataclasses import replace
from typing import Iterable

from .models import LevelClass, LevelLifecycle, TechnicalLevel, WaveHypothesis


NON_ACTIONABLE_STATES = {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}


def _distance_atr(level: TechnicalLevel) -> float:
    value = level.distance_atr
    return abs(float(value)) if value is not None and math.isfinite(float(value)) else math.inf


def classify_distance(level: TechnicalLevel) -> LevelClass:
    distance = _distance_atr(level)
    if level.lifecycle_state in NON_ACTIONABLE_STATES or distance > 4.0:
        return LevelClass.STRUCTURAL
    if distance <= 1.5:
        return LevelClass.NEAR_TERM
    return LevelClass.SECONDARY


def role_side(level: TechnicalLevel, price: float) -> str:
    """Seviyenin mevcut fiyata göre pratik tarafını söyler.

    Kırılmış eski destek fiyatın üstündeyse yeniden kazanım direncidir; source
    adının LOW olması onu tekrar destek yapmaz.
    """
    if level.value > price:
        return "ABOVE"
    if level.value < price:
        return "BELOW"
    return "AT_PRICE"


def rank_levels(levels: Iterable[TechnicalLevel], price: float) -> list[TechnicalLevel]:
    """Seviyeleri güncellik, yakınlık ve yapısal önemle sıralar."""
    ranked: list[TechnicalLevel] = []
    for original in levels:
        level_class = classify_distance(original)
        distance = _distance_atr(original)
        proximity = 0.0 if not math.isfinite(distance) else 1.0 / (1.0 + distance)
        lifecycle_factor = {
            LevelLifecycle.ACTIVE: 1.0,
            LevelLifecycle.TESTED: 1.0,
            LevelLifecycle.RECLAIMED: 0.9,
            LevelLifecycle.BROKEN_UP: 0.75,
            LevelLifecycle.BROKEN_DOWN: 0.75,
            LevelLifecycle.REJECTED: 0.65,
            LevelLifecycle.STALE: 0.05,
            LevelLifecycle.INVALIDATED: 0.0,
        }[original.lifecycle_state]
        actionability = proximity * lifecycle_factor
        if level_class == LevelClass.STRUCTURAL:
            actionability *= 0.25
        priority = min(original.confidence * 0.45 + actionability * 0.55, 1.0)
        metadata = dict(original.metadata)
        metadata["price_side"] = role_side(original, price)
        ranked.append(
            replace(
                original,
                level_class=level_class,
                actionability=actionability,
                priority=priority,
                metadata=metadata,
            )
        )
    return sorted(
        ranked,
        key=lambda item: (
            item.lifecycle_state in NON_ACTIONABLE_STATES,
            item.level_class == LevelClass.STRUCTURAL,
            -item.priority,
            _distance_atr(item),
        ),
    )


def nearest_active_levels(
    levels: Iterable[TechnicalLevel],
    price: float,
    per_side: int = 3,
) -> dict[str, list[TechnicalLevel]]:
    """Güncel karar için yakın alt/üst seviyeleri verir.

    STRUCTURAL veya STALE seviyeler güncel tetik listesine sokulmaz. Böylece
    ZGYO 21 iken 27.98/40.50 gibi uzak yapısal değerler ana karar eşikleri
    olarak sunulamaz.
    """
    ranked = rank_levels(levels, price)
    eligible = [
        item
        for item in ranked
        if item.lifecycle_state not in NON_ACTIONABLE_STATES
        and item.level_class != LevelClass.STRUCTURAL
    ]
    below = [item for item in eligible if item.value < price]
    above = [item for item in eligible if item.value > price]
    below.sort(key=lambda item: abs(item.value - price))
    above.sort(key=lambda item: abs(item.value - price))
    return {"below": below[:per_side], "above": above[:per_side]}


def structural_levels(levels: Iterable[TechnicalLevel]) -> list[TechnicalLevel]:
    return [
        item
        for item in levels
        if classify_distance(item) == LevelClass.STRUCTURAL
        or item.lifecycle_state in NON_ACTIONABLE_STATES
    ]


def wave_levels(
    hypotheses: Iterable[WaveHypothesis],
    price: float,
    atr: float | None = None,
) -> list[TechnicalLevel]:
    """Elliott invalidation ve hedef bölgelerini ortak level modeline çevirir."""
    result: list[TechnicalLevel] = []
    for hypothesis in hypotheses:
        if not hypothesis.hard_rule_valid:
            continue
        if hypothesis.invalidation_level is not None:
            value = float(hypothesis.invalidation_level)
            distance_atr = (value - price) / atr if atr and atr > 0 else None
            result.append(
                TechnicalLevel(
                    value=value,
                    source="ELLIOTT_INVALIDATION",
                    role="WAVE_INVALIDATION",
                    distance_pct=(value / price - 1.0) * 100 if price else None,
                    distance_atr=distance_atr,
                    confidence=hypothesis.confidence,
                    metadata={"wave_id": hypothesis.id, "pattern": hypothesis.pattern_type},
                )
            )
        for index, (low, high) in enumerate(hypothesis.target_zones, start=1):
            midpoint = (float(low) + float(high)) / 2.0
            distance_atr = (midpoint - price) / atr if atr and atr > 0 else None
            result.append(
                TechnicalLevel(
                    value=midpoint,
                    zone_low=float(low),
                    zone_high=float(high),
                    source="ELLIOTT_TARGET",
                    role="WAVE_TARGET_ZONE",
                    distance_pct=(midpoint / price - 1.0) * 100 if price else None,
                    distance_atr=distance_atr,
                    confidence=hypothesis.confidence,
                    metadata={
                        "wave_id": hypothesis.id,
                        "pattern": hypothesis.pattern_type,
                        "target_index": index,
                    },
                )
            )
    return result
