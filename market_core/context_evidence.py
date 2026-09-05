from __future__ import annotations

from typing import Any

from .models import Evidence, EvidenceDirection


def _direction(value: str) -> EvidenceDirection:
    value = str(value).upper()
    if value in {"BULLISH", "UP"}:
        return EvidenceDirection.BULLISH
    if value in {"BEARISH", "DOWN"}:
        return EvidenceDirection.BEARISH
    if value in {"UNCERTAINTY", "UNAVAILABLE"}:
        return EvidenceDirection.UNCERTAINTY
    return EvidenceDirection.NEUTRAL


def regime_evidence(regime: dict[str, Any]) -> list[Evidence]:
    state = str(regime.get("state", "INSUFFICIENT"))
    confidence = float(regime.get("confidence", 0.0) or 0.0)
    if state == "DIRECTIONAL_TREND_UP":
        direction = EvidenceDirection.BULLISH
        strength = 0.75
    elif state == "DIRECTIONAL_TREND_DOWN":
        direction = EvidenceDirection.BEARISH
        strength = 0.75
    elif state in {"SQUEEZE", "TRANSITION", "HIGH_VOL_NON_DIRECTIONAL", "INSUFFICIENT"}:
        direction = EvidenceDirection.UNCERTAINTY
        strength = 0.55
    else:
        direction = EvidenceDirection.NEUTRAL
        strength = 0.45
    return [
        Evidence(
            family="regime",
            direction=direction,
            state=state,
            strength=strength,
            confidence=max(min(confidence, 1.0), 0.25),
            independent_group="regime",
            reason=" ".join(str(item) for item in regime.get("reasons", [])) or "Rejim sınıflaması.",
        )
    ]


def relative_strength_evidence(relative_strength: dict[str, Any]) -> list[Evidence]:
    if not relative_strength.get("available"):
        return [
            Evidence(
                family="relative_strength",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Benchmark yok",
                strength=0.25,
                confidence=0.8,
                independent_group="relative_strength",
                reason=str(relative_strength.get("reason", "Benchmark verisi sağlanmadı.")),
            )
        ]
    direction = _direction(str(relative_strength.get("direction", "NEUTRAL")))
    consistency = float(relative_strength.get("consistency", 0.0) or 0.0)
    return [
        Evidence(
            family="relative_strength",
            direction=direction,
            state=str(relative_strength.get("state", "MIXED")),
            strength=max(0.35, min(consistency, 1.0)),
            confidence=0.85,
            independent_group="relative_strength",
            reason=f"{relative_strength.get('benchmark', 'benchmark')} karşısında relatif performans; fon akışı değildir.",
        )
    ]


def multi_timeframe_evidence(mtf: dict[str, Any]) -> list[Evidence]:
    if not mtf.get("available"):
        return [
            Evidence(
                family="multi_timeframe",
                direction=EvidenceDirection.UNCERTAINTY,
                state="Ek zaman dilimi yok",
                strength=0.20,
                confidence=0.75,
                independent_group="multi_timeframe",
                reason=str(mtf.get("reason", "Ek zaman dilimi sağlanmadı.")),
            )
        ]
    state = str(mtf.get("state", "DIVERGENT"))
    if state == "ALIGNED":
        direction = _direction(str(mtf.get("direction", "NEUTRAL")))
        strength = max(0.45, min(float(mtf.get("alignment", 0.0) or 0.0), 1.0))
    else:
        direction = EvidenceDirection.UNCERTAINTY
        strength = max(0.35, 1.0 - float(mtf.get("alignment", 0.0) or 0.0))
    return [
        Evidence(
            family="multi_timeframe",
            direction=direction,
            state=state,
            strength=strength,
            confidence=0.85,
            independent_group="multi_timeframe",
            reason=str(mtf.get("reason", "Zaman dilimi uyumu/ayrışması.")),
        )
    ]
