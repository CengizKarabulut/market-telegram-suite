from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import pandas as pd

from .elliott import build_wave_hypotheses
from .levels import nearest_active_levels, rank_levels, structural_levels, wave_levels
from .models import MarketState, TechnicalLevel
from .scenario import (
    assert_no_completed_condition_is_pending,
    condition_from_level,
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


def _scenario_levels(level_map: dict[str, list[TechnicalLevel]]) -> list:
    """Yakın aktif seviyelerden iki yönlü, gerçekleşmemiş senaryolar üretir."""
    conditions = []
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
    """V3 çekirdeğinin ilk uçtan uca canonical state üreticisi.

    Girdi veri çerçevesinin en az OHLC kolonlarını içermesi beklenir. ATR varsa
    pivot prominence ve seviye mesafelerinde kullanılır. Bu fonksiyon yorum
    metni veya Telegram çıktısı üretmez; bütün downstream katmanlar aynı state'i
    okuyacaktır.
    """
    required = {"Open", "High", "Low", "Close"}
    missing = sorted(required.difference(data.columns))
    if missing:
        raise ValueError(f"MarketState için eksik kolonlar: {', '.join(missing)}")
    if len(data) < 8:
        raise ValueError("MarketState için en az 8 bar gerekir.")

    price = float(data["Close"].iloc[-1])
    structure = build_structure_state(data)
    pivots = structure.get("pivots", [])
    waves = build_wave_hypotheses(pivots, timeframe=interval)

    levels: list[TechnicalLevel] = list(structure.get("levels", []))
    levels.extend(wave_levels(waves, price=price, atr=_atr(data)))
    levels = rank_levels(levels, price)
    active = nearest_active_levels(levels, price)

    raw_conditions = [
        condition_from_level(level, price, side)
        for level, side in _scenario_levels(active)
    ]
    assert_no_completed_condition_is_pending(raw_conditions, price)
    scenarios = pending_conditions(raw_conditions)

    # Structure dict içinde dataclass nesneleri korunur; JSON/presentation katmanı
    # ihtiyaç duyduğunda serialize eder. Burada ayrıca hızlı tüketim için özet var.
    structure_summary = {
        **structure,
        "nearest_levels": active,
        "structural_levels": structural_levels(levels),
    }

    quality = dict(data_quality or {})
    critical = bool(quality.get("critical")) or str(quality.get("state", "")).upper() in {"INVALID", "CRITICAL"}
    limitations: list[str] = []
    if critical:
        limitations.append("Kritik veri kalitesi sorunu: yorum ve yön çıkarımı presentation katmanında kapatılmalıdır.")

    return MarketState(
        symbol=symbol,
        timestamp=data.index[-1],
        interval=interval,
        price=price,
        change_pct=_change_pct(data),
        bar_state=dict(bar_state or {}),
        data_quality=quality,
        indicators=dict(indicators or {}),
        structure=structure_summary,
        wave_hypotheses=waves,
        levels=levels,
        scenarios=[asdict(item) for item in scenarios],
        limitations=limitations,
        confidence={
            "wave_primary": waves[0].confidence if waves else None,
            "structure_available": structure.get("state") != "INSUFFICIENT",
            "critical_data_quality": critical,
        },
    )
