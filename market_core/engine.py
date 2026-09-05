from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import pandas as pd

from .context_evidence import multi_timeframe_evidence, regime_evidence, relative_strength_evidence
from .elliott import build_wave_hypotheses
from .evidence import build_evidence, summarize_evidence
from .interpretation import build_interpretation
from .levels import nearest_active_levels, rank_levels, structural_levels, wave_levels
from .models import MarketState, TechnicalLevel
from .multi_timeframe import build_multi_timeframe
from .regime import build_regime
from .relative_strength import build_relative_strength
from .scenario import (
    assert_no_completed_condition_is_pending,
    condition_from_level,
    deduplicate_conditions,
    pending_conditions,
)
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
    benchmark_data: pd.DataFrame | None = None,
    benchmark_name: str = "BENCHMARK",
    multi_timeframe_states: dict[str, dict[str, Any]] | None = None,
) -> MarketState:
    """Tek canonical V3 market state üretir."""
    required = {"Open", "High", "Low", "Close"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"MarketState için eksik kolonlar: {', '.join(missing)}")
    if len(data) < 8:
        raise ValueError("MarketState için en az 8 bar gerekir.")

    price = _number(data["Close"].iloc[-1])
    if not math.isfinite(price):
        raise ValueError("MarketState için son kapanış fiyatı geçerli olmalıdır.")

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
    scenario_objects = deduplicate_conditions(pending_conditions(raw_conditions))

    quality = dict(data_quality or {})
    critical = bool(quality.get("critical")) or str(quality.get("state", "")).upper() in {"INVALID", "CRITICAL"}
    limitations: list[str] = []
    if critical:
        limitations.append("Kritik veri kalitesi sorunu: yön ve seviye yorumu hard-gate edildi.")
        scenario_objects = []
    scenarios = [asdict(item) for item in scenario_objects]

    structure_summary = {
        **structure,
        "nearest_levels": active,
        "structural_levels": structural_levels(levels),
    }

    regime = build_regime(data, indicator_values)
    relative_strength = build_relative_strength(data, benchmark_data, benchmark_name=benchmark_name)
    multi_timeframe = build_multi_timeframe(interval, multi_timeframe_states)

    evidence, _ = build_evidence(
        structure=structure_summary,
        hypotheses=waves,
        levels=levels,
        price=price,
        indicators=indicator_values,
    )
    evidence.extend(regime_evidence(regime))
    evidence.extend(relative_strength_evidence(relative_strength))
    evidence.extend(multi_timeframe_evidence(multi_timeframe))
    evidence_summary = summarize_evidence(evidence)

    interpretation = build_interpretation(
        price=price,
        structure=structure_summary,
        waves=waves,
        levels=levels,
        scenarios=scenarios,
        evidence=evidence,
        evidence_summary=evidence_summary,
        critical_data_quality=critical,
        regime=regime,
        relative_strength=relative_strength,
        multi_timeframe=multi_timeframe,
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
        regime=regime,
        evidence=evidence,
        evidence_summary=evidence_summary,
        scenarios=scenarios,
        interpretation=interpretation,
        relative_strength=relative_strength,
        multi_timeframe=multi_timeframe,
        limitations=limitations,
        confidence={
            "wave_primary": waves[0].confidence if waves else None,
            "structure_available": structure.get("state") != "INSUFFICIENT",
            "critical_data_quality": critical,
            "evidence_clarity": evidence_summary.get("clarity"),
            "directional_bias": evidence_summary.get("directional_bias"),
            "regime_confidence": regime.get("confidence"),
            "relative_strength_available": relative_strength.get("available"),
            "multi_timeframe_available": multi_timeframe.get("available"),
        },
    )
