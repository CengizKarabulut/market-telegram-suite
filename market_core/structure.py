from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .models import LevelLifecycle, Pivot, StructureEvent, TechnicalLevel


def _number(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _atr_at(data: pd.DataFrame, index: int) -> float:
    if "ATR" not in data.columns:
        return math.nan
    return _number(data["ATR"].iloc[index])


def detect_confirmed_pivots(
    data: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    min_prominence_atr: float = 0.35,
) -> list[Pivot]:
    """Teyitli pivotları yalnız geçmiş ve sağ teyit barlarıyla üretir.

    Pivot gücü, çevre fiyatlardan uzaklığın ATR'ye oranıyla yaklaşıklandırılır.
    Sağ teyit zorunlu olduğu için son `right` bar hiçbir zaman pivot sayılmaz.
    """
    if len(data) < left + right + 3:
        return []
    highs = data["High"].to_numpy(dtype=float)
    lows = data["Low"].to_numpy(dtype=float)
    pivots: list[Pivot] = []
    for i in range(left, len(data) - right):
        high_window = highs[i - left : i + right + 1]
        low_window = lows[i - left : i + right + 1]
        atr = _atr_at(data, i)
        local_high = highs[i] >= np.nanmax(high_window)
        local_low = lows[i] <= np.nanmin(low_window)
        if local_high:
            neighborhood = np.delete(high_window, left)
            prominence = highs[i] - float(np.nanmax(neighborhood)) if len(neighborhood) else 0.0
            prominence_atr = prominence / atr if atr > 0 else 0.0
            if prominence_atr >= min_prominence_atr or not math.isfinite(atr):
                pivots.append(Pivot(i, data.index[i], float(highs[i]), "HIGH", prominence_atr=prominence_atr, strength=prominence_atr))
        if local_low:
            neighborhood = np.delete(low_window, left)
            prominence = float(np.nanmin(neighborhood)) - lows[i] if len(neighborhood) else 0.0
            prominence_atr = prominence / atr if atr > 0 else 0.0
            if prominence_atr >= min_prominence_atr or not math.isfinite(atr):
                pivots.append(Pivot(i, data.index[i], float(lows[i]), "LOW", prominence_atr=prominence_atr, strength=prominence_atr))
    pivots.sort(key=lambda item: item.index)
    return _collapse_same_kind(pivots)


def _collapse_same_kind(pivots: list[Pivot]) -> list[Pivot]:
    """Ardışık aynı tip pivotlarda yalnız daha ekstrem olanı korur."""
    if not pivots:
        return []
    result = [pivots[0]]
    for pivot in pivots[1:]:
        previous = result[-1]
        if pivot.kind != previous.kind:
            result.append(pivot)
            continue
        if pivot.kind == "HIGH" and pivot.price > previous.price:
            result[-1] = pivot
        elif pivot.kind == "LOW" and pivot.price < previous.price:
            result[-1] = pivot
    return result


def assign_pivot_degrees(pivots: list[Pivot]) -> list[Pivot]:
    """Pivotları prominence'e göre micro/minor/intermediate derecelerine ayırır."""
    if not pivots:
        return []
    strengths = np.array([max(item.strength, 0.0) for item in pivots], dtype=float)
    if np.allclose(strengths, strengths[0]):
        q50 = q80 = strengths[0]
    else:
        q50, q80 = np.nanquantile(strengths, [0.50, 0.80])
    result = []
    for item in pivots:
        degree = "intermediate" if item.strength >= q80 else "minor" if item.strength >= q50 else "micro"
        result.append(Pivot(**{**asdict(item), "degree": degree}))
    return result


def classify_structure(pivots: list[Pivot]) -> dict[str, Any]:
    highs = [item for item in pivots if item.kind == "HIGH"]
    lows = [item for item in pivots if item.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return {"state": "INSUFFICIENT", "high_state": None, "low_state": None}
    high_state = "HH" if highs[-1].price > highs[-2].price else "LH"
    low_state = "HL" if lows[-1].price > lows[-2].price else "LL"
    state = f"{high_state}/{low_state}"
    bias = "BULLISH" if state == "HH/HL" else "BEARISH" if state == "LH/LL" else "TRANSITION"
    return {
        "state": state,
        "bias": bias,
        "high_state": high_state,
        "low_state": low_state,
        "last_high": highs[-1],
        "last_low": lows[-1],
        "previous_high": highs[-2],
        "previous_low": lows[-2],
    }


def detect_structure_events(data: pd.DataFrame, pivots: list[Pivot]) -> list[StructureEvent]:
    """Teyitli pivot seviyelerinde kapanış bazlı BOS olaylarını üretir."""
    close = data["Close"].to_numpy(dtype=float)
    events: list[StructureEvent] = []
    for pivot in pivots:
        for i in range(pivot.index + 1, len(data)):
            previous = close[i - 1]
            current = close[i]
            if pivot.kind == "HIGH" and previous <= pivot.price < current:
                events.append(StructureEvent("BOS_UP", pivot.price, pivot.index, i, float(current)))
                break
            if pivot.kind == "LOW" and previous >= pivot.price > current:
                events.append(StructureEvent("BOS_DOWN", pivot.price, pivot.index, i, float(current)))
                break
    return sorted(events, key=lambda item: item.trigger_index)


def swing_level_from_pivot(pivot: Pivot, price: float, last_index: int) -> TechnicalLevel:
    """Pivotun bugünkü fiyatla rolünü ve lifecycle durumunu belirler."""
    broken_down = pivot.kind == "LOW" and price < pivot.price
    broken_up = pivot.kind == "HIGH" and price > pivot.price
    if broken_down:
        lifecycle = LevelLifecycle.BROKEN_DOWN
        role = "FORMER_SUPPORT_RECLAIM"
        direction = "UP"
    elif broken_up:
        lifecycle = LevelLifecycle.BROKEN_UP
        role = "FORMER_RESISTANCE_RETEST"
        direction = "DOWN"
    else:
        lifecycle = LevelLifecycle.ACTIVE
        role = "SUPPORT" if pivot.kind == "LOW" else "RESISTANCE"
        direction = "DOWN" if pivot.kind == "LOW" else "UP"
    distance_pct = (pivot.price / price - 1.0) * 100 if price else None
    return TechnicalLevel(
        value=pivot.price,
        source=f"SWING_{pivot.kind}",
        role=role,
        lifecycle_state=lifecycle,
        direction=direction,
        distance_pct=distance_pct,
        age_bars=max(last_index - pivot.index, 0),
        broken=broken_down or broken_up,
        confidence=min(max(0.5 + pivot.strength / 4.0, 0.0), 1.0),
        metadata={"pivot_index": pivot.index, "pivot_degree": pivot.degree},
    )


def build_structure_state(data: pd.DataFrame) -> dict[str, Any]:
    pivots = assign_pivot_degrees(detect_confirmed_pivots(data))
    structure = classify_structure(pivots)
    events = detect_structure_events(data, pivots)
    price = float(data["Close"].iloc[-1])
    levels = [swing_level_from_pivot(item, price, len(data) - 1) for item in pivots[-8:]]
    if structure.get("last_low"):
        last_low: Pivot = structure["last_low"]
        structure["last_low_broken"] = price < last_low.price
    if structure.get("last_high"):
        last_high: Pivot = structure["last_high"]
        structure["last_high_broken"] = price > last_high.price
    structure.update({"pivots": pivots, "events": events, "levels": levels})
    return structure
