from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import pandas as pd

from .elliott import build_wave_hypotheses
from .evidence import build_evidence
from .interpretation import build_interpretation
from .levels import nearest_active_levels, rank_levels, structural_levels, wave_levels
from .models import MarketState, TechnicalLevel
from .scenario import assert_no_completed_condition_is_pending, condition_from_level, pending_conditions
from .structure import build_structure_state


def _number(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _atr(data: pd.DataFrame) -> float | None:
    if "ATR" not in data.columns:
        return None
    value = _number(data["ATR"].iloc[-1])
    return value if math.isfinite(value) and value > 0 else None


def _change_pct(data: pd.DataFrame) -> float:
    if len(data) < 2:
        return 0.0
    current = _number(data["Close"].iloc[-1])
    previous = _number(data["Close"].iloc[-2])
    return (current / previous - 1.0) * 100 if previous else 0.0


def _scenario_levels(level_map: dict[str, list[TechnicalLevel]]) -> list[tuple[TechnicalLevel, str]]:
    conditions: list[tuple[TechnicalLevel, str]] = []
    for level in level_map.get("above", []):
        conditions.append((level, "UP"))
    for level in level_map.get("below", []):
        conditions.append((level, "DOWN"))
    return conditions


def build_market_state(
    data: pd.DataFrame,
    symbol: str,
    interval: str = "1d",
    *,
    bar_state: dict[str, Any] | None = None,
    data_quality: dict[str, Any] | None = None,
    indicators: dict[str, Any] | None = None,
) -> MarketState:
    """Tek canonical V3 market state üretir.

    Downstream Telegram/görsel katmanları kendi teknik hesabını yapmayacak;
    structure, Elliott, level, evidence ve interpretation aynı state üzerinden
    beslenecek.
    """
    required = {"Open", "High", "Low", "Close"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"MarketState için eksik kolonlar: {', '.join(missing)}")
    if len(data) < 8:
        raise ValueError("MarketState için en az 8 bar gerekir.")

    price = float(data["Close"].iloc[-1])
    indicator_values = dict(indicators or {})
    structure = build_structure_state(data)
    pivots = structure.get("pivots", [])
    waves = build_wave_hypotheses(pivots, timeframe=interval)

    levels: list[TechnicalLevel] = list(structure.get("levels", []))
    levels.extend(wave_levels(waves, price=price, atr=_atr(data)))
    levels = rank_levels(levels, price)
    active = nearest_active_levels(levels, price)

    raw_conditions = [condition_from_level(level, price, side) for level, side in _scenario_levels(active)]
    assert_no_completed_condition_is_pending(raw_conditions, price)
    scenario_objects = pending_conditions(raw_conditions)
    scenarios = [asdict(item) for item in scenario_objects]

    structure_summary = {
        **structure,
        "nearest_levels": active,
        "structural_levels": structural_levels(levels),
    }

    quality = dict(data_quality or {})
    critical = bool(quality.get("critical")) or str(quality.get("state", "")).upper() in {"INVALID", "CRITICAL"}
    limitations: list[str] = []
    if critical:
        limitations.append("Kritik veri kalitesi sorunu: yön ve seviye yorumu hard-gate edildi.")

    evidence, evidence_summary = build_evidence(
        structure=structure_summary,
        hypotheses=waves,
        levels=levels,
        price=price,
        indicators=indicator_values,
    )
    interpretation = build_interpretation(
        price=price,
        structure=structure_summary,
        waves=waves,
        levels=levels,
        scenarios=scenarios,
        evidence=evidence,
        evidence_summary=evidence_summary,
        critical_data_quality=critical,
    )

    return MarketState(
        symbol=symbol,
        timestamp=data.index[-1],
        interval=interval,
        price=price,
        change_pct=_change_pct(data),
        bar_state=dict(bar_state or {}),
        data_quality=quality,
        indicators=indicator_values,
        structure=structure_summary,
        wave_hypotheses=waves,
        levels=levels,
        evidence=evidence,
        evidence_summary=evidence_summary,
        scenarios=scenarios,
        interpretation=interpretation,
        limitations=limitations,
        confidence={
            "wave_primary": waves[0].confidence if waves else None,
            "structure_available": structure.get("state") != "INSUFFICIENT",
            "critical_data_quality": critical,
            "evidence_clarity": evidence_summary.get("clarity"),
            "directional_bias": evidence_summary.get("directional_bias"),
        },
    )
