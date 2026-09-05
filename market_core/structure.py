from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .models import LevelClass, LevelLifecycle, Pivot, StructureEvent, TechnicalLevel


def _number(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _atr_at(data: pd.DataFrame | None, index: int) -> float:
    if data is None or "ATR" not in data.columns or not len(data):
        return math.nan
    index = min(max(index, 0), len(data) - 1)
    return _number(data["ATR"].iloc[index])


def detect_confirmed_pivots(
    data: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    min_prominence_atr: float = 0.35,
) -> list[Pivot]:
    """Sadece sağ teyidi tamamlanmış pivotları üretir.

    `confirmed_index` pivot fiyatının görüldüğü bar değil, downstream motorların
    bu pivotu ilk kez kullanabileceği bardır. Böylece structure ve Elliott
    tarafında look-ahead bias oluşmaz.
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
                pivots.append(
                    Pivot(
                        i,
                        data.index[i],
                        float(highs[i]),
                        "HIGH",
                        prominence_atr=prominence_atr,
                        strength=prominence_atr,
                        confirmed_index=i + right,
                    )
                )
        if local_low:
            neighborhood = np.delete(low_window, left)
            prominence = float(np.nanmin(neighborhood)) - lows[i] if len(neighborhood) else 0.0
            prominence_atr = prominence / atr if atr > 0 else 0.0
            if prominence_atr >= min_prominence_atr or not math.isfinite(atr):
                pivots.append(
                    Pivot(
                        i,
                        data.index[i],
                        float(lows[i]),
                        "LOW",
                        prominence_atr=prominence_atr,
                        strength=prominence_atr,
                        confirmed_index=i + right,
                    )
                )
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
    """Prominence dağılımına göre micro/minor/intermediate derece verir."""
    if not pivots:
        return []
    strengths = np.array([max(item.strength, 0.0) for item in pivots], dtype=float)
    if np.allclose(strengths, strengths[0]):
        q50 = q80 = strengths[0]
    else:
        q50, q80 = np.nanquantile(strengths, [0.50, 0.80])
    result: list[Pivot] = []
    for item in pivots:
        degree = "intermediate" if item.strength >= q80 else "minor" if item.strength >= q50 else "micro"
        result.append(Pivot(**{**asdict(item), "degree": degree}))
    return result


def classify_structure(pivots: list[Pivot]) -> dict[str, Any]:
    highs = [item for item in pivots if item.kind == "HIGH"]
    lows = [item for item in pivots if item.kind == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return {"state": "INSUFFICIENT", "bias": "TRANSITION", "high_state": None, "low_state": None}
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


def _structure_bias_before(pivots: list[Pivot], bar_index: int) -> str:
    """Belirli bar kapanmadan önce gerçekten bilinebilen yapıyı döndürür."""
    known = [
        item
        for item in pivots
        if (item.confirmed_index if item.confirmed_index is not None else item.index) <= bar_index
    ]
    return str(classify_structure(known).get("bias", "TRANSITION"))


def detect_structure_events(data: pd.DataFrame, pivots: list[Pivot]) -> list[StructureEvent]:
    """Kapanış bazlı BOS/CHoCH üretir.

    CHoCH etiketi pivotun teyit edildiği andaki değil, kırılım gerçekleşmeden
    hemen önce bilinen yapının yönüne göre verilir. Böylece daha sonra oluşan
    pivotların geçmiş olayı yeniden etiketlemesi önlenir.
    """
    close = data["Close"].to_numpy(dtype=float)
    events: list[StructureEvent] = []
    for pivot in pivots:
        first_usable = pivot.confirmed_index if pivot.confirmed_index is not None else pivot.index
        start = max(first_usable + 1, pivot.index + 1)
        for i in range(start, len(data)):
            previous = close[i - 1]
            current = close[i]
            broke_up = pivot.kind == "HIGH" and previous <= pivot.price < current
            broke_down = pivot.kind == "LOW" and previous >= pivot.price > current
            if not (broke_up or broke_down):
                continue
            prior_bias = _structure_bias_before(pivots, i - 1)
            if broke_up:
                kind = "CHOCH_UP" if prior_bias == "BEARISH" else "BOS_UP"
            else:
                kind = "CHOCH_DOWN" if prior_bias == "BULLISH" else "BOS_DOWN"
            events.append(
                StructureEvent(
                    kind=kind,
                    level=pivot.price,
                    pivot_index=pivot.index,
                    trigger_index=i,
                    trigger_price=float(current),
                    prior_bias=prior_bias,
                    pivot_confirmed_index=first_usable,
                )
            )
            break
    return sorted(events, key=lambda item: (item.trigger_index, item.pivot_index))


def _cross_indices(close: np.ndarray, level: float, start: int, direction: str) -> list[int]:
    indices: list[int] = []
    for i in range(max(start, 1), len(close)):
        if direction == "DOWN" and close[i - 1] >= level > close[i]:
            indices.append(i)
        elif direction == "UP" and close[i - 1] <= level < close[i]:
            indices.append(i)
    return indices


def _test_count(data: pd.DataFrame, pivot: Pivot, tolerance: float) -> int:
    """Teyitten sonra seviyeye dokunan fakat ilk rolünü koruyan barları sayar."""
    start = (pivot.confirmed_index if pivot.confirmed_index is not None else pivot.index) + 1
    if start >= len(data):
        return 0
    tests = 0
    for row in data.iloc[start:].itertuples():
        if pivot.kind == "LOW":
            touched = float(row.Low) <= pivot.price + tolerance
            held = float(row.Close) >= pivot.price
        else:
            touched = float(row.High) >= pivot.price - tolerance
            held = float(row.Close) <= pivot.price
        if touched and held:
            tests += 1
    return tests


def _post_break_touch_indices(
    data: pd.DataFrame,
    pivot: Pivot,
    first_break: int,
    tolerance: float,
) -> list[int]:
    """Kırılım sonrası seviyenin diğer taraftan test edildiği barları bulur."""
    indices: list[int] = []
    for i in range(first_break + 1, len(data)):
        row = data.iloc[i]
        if pivot.kind == "LOW":
            # Eski desteğe aşağıdan yükselip kapanışın yine altında kalması.
            if float(row["High"]) >= pivot.price - tolerance and float(row["Close"]) < pivot.price:
                indices.append(i)
        else:
            # Eski dirence yukarıdan geri test ve kapanışın üstte kalması.
            if float(row["Low"]) <= pivot.price + tolerance and float(row["Close"]) > pivot.price:
                indices.append(i)
    return indices


def _lifecycle_history(
    data: pd.DataFrame,
    pivot: Pivot,
    tolerance: float,
) -> dict[str, Any]:
    close = data["Close"].to_numpy(dtype=float)
    start = (pivot.confirmed_index if pivot.confirmed_index is not None else pivot.index) + 1
    break_direction = "DOWN" if pivot.kind == "LOW" else "UP"
    return_direction = "UP" if pivot.kind == "LOW" else "DOWN"
    breaks = _cross_indices(close, pivot.price, start, break_direction)
    if not breaks:
        return {
            "first_break": None,
            "last_transition": None,
            "return_crosses": [],
            "rebreaks": [],
            "post_break_touches": [],
            "events": [],
        }

    first_break = breaks[0]
    returns = _cross_indices(close, pivot.price, first_break + 1, return_direction)
    rebreaks: list[int] = []
    if returns:
        rebreaks = _cross_indices(close, pivot.price, returns[-1] + 1, break_direction)
    touches = _post_break_touch_indices(data, pivot, first_break, tolerance)
    events: list[dict[str, Any]] = [
        {"index": first_break, "event": "BREAK_DOWN" if pivot.kind == "LOW" else "BREAK_UP"}
    ]
    for index in returns:
        events.append(
            {
                "index": index,
                "event": "RECLAIM_SUPPORT" if pivot.kind == "LOW" else "BREAKOUT_REJECTED",
            }
        )
    for index in touches:
        events.append(
            {
                "index": index,
                "event": "RECLAIM_REJECTED" if pivot.kind == "LOW" else "RETEST_HELD",
            }
        )
    for index in rebreaks:
        events.append(
            {
                "index": index,
                "event": "RECLAIM_FAILED" if pivot.kind == "LOW" else "BREAKOUT_RECLAIMED",
            }
        )
    events.sort(key=lambda item: int(item["index"]))
    return {
        "first_break": first_break,
        "last_transition": events[-1]["index"] if events else first_break,
        "return_crosses": returns,
        "rebreaks": rebreaks,
        "post_break_touches": touches,
        "events": events,
    }


def swing_level_from_pivot(
    pivot: Pivot,
    price: float,
    last_index: int,
    data: pd.DataFrame | None = None,
    stale_after: int = 120,
) -> TechnicalLevel:
    """Pivot seviyesinin bütün lifecycle geçmişini bugünkü duruma taşır."""
    age = max(last_index - pivot.index, 0)
    atr = _atr_at(data, last_index)
    distance_atr = (pivot.price - price) / atr if atr > 0 else None
    distance_pct = (pivot.price / price - 1.0) * 100 if price else None
    tolerance = atr * 0.10 if atr > 0 else abs(pivot.price) * 0.0025
    tests = _test_count(data, pivot, tolerance) if data is not None and len(data) else 0
    history = (
        _lifecycle_history(data, pivot, tolerance)
        if data is not None and len(data)
        else {
            "first_break": None,
            "last_transition": None,
            "return_crosses": [],
            "rebreaks": [],
            "post_break_touches": [],
            "events": [],
        }
    )
    first_break = history["first_break"]
    ever_broken = first_break is not None
    current_broken = (pivot.kind == "LOW" and price < pivot.price) or (pivot.kind == "HIGH" and price > pivot.price)

    if age >= stale_after and abs(distance_atr if distance_atr is not None else 99.0) > 4.0:
        lifecycle = LevelLifecycle.STALE
        role = "HISTORICAL_STRUCTURE"
    elif pivot.kind == "LOW" and ever_broken:
        if price >= pivot.price:
            lifecycle = LevelLifecycle.RECLAIMED
            role = "RECLAIMED_SUPPORT"
        elif history["rebreaks"]:
            lifecycle = LevelLifecycle.REJECTED
            role = "RECLAIM_FAILED_SUPPORT"
        elif history["post_break_touches"]:
            lifecycle = LevelLifecycle.REJECTED
            role = "FORMER_SUPPORT_REJECTION"
        else:
            lifecycle = LevelLifecycle.BROKEN_DOWN
            role = "FORMER_SUPPORT_RECLAIM"
    elif pivot.kind == "HIGH" and ever_broken:
        if price <= pivot.price:
            lifecycle = LevelLifecycle.REJECTED
            role = "BREAKOUT_REJECTED_RESISTANCE"
        elif history["rebreaks"]:
            lifecycle = LevelLifecycle.RECLAIMED
            role = "BREAKOUT_RECLAIMED_SUPPORT"
        elif history["post_break_touches"]:
            lifecycle = LevelLifecycle.TESTED
            role = "FORMER_RESISTANCE_RETEST_HELD"
        else:
            lifecycle = LevelLifecycle.BROKEN_UP
            role = "FORMER_RESISTANCE_RETEST"
    elif current_broken:
        lifecycle = LevelLifecycle.BROKEN_DOWN if pivot.kind == "LOW" else LevelLifecycle.BROKEN_UP
        role = "FORMER_SUPPORT_RECLAIM" if pivot.kind == "LOW" else "FORMER_RESISTANCE_RETEST"
    elif tests > 0:
        lifecycle = LevelLifecycle.TESTED
        role = "SUPPORT" if pivot.kind == "LOW" else "RESISTANCE"
    else:
        lifecycle = LevelLifecycle.ACTIVE
        role = "SUPPORT" if pivot.kind == "LOW" else "RESISTANCE"

    absolute_atr = abs(distance_atr) if distance_atr is not None else math.inf
    if lifecycle == LevelLifecycle.STALE or absolute_atr > 4.0:
        level_class = LevelClass.STRUCTURAL
    elif absolute_atr <= 1.5:
        level_class = LevelClass.NEAR_TERM
    else:
        level_class = LevelClass.SECONDARY

    proximity = 1.0 / (1.0 + absolute_atr) if math.isfinite(absolute_atr) else 0.25
    degree_weight = {"micro": 0.55, "minor": 0.75, "intermediate": 1.0}.get(pivot.degree, 0.7)
    confidence = min(max(0.45 + pivot.strength / 4.0 + min(tests, 3) * 0.05, 0.0), 1.0)
    actionability = 0.0 if lifecycle == LevelLifecycle.STALE else min(proximity * degree_weight, 1.0)
    priority = min(confidence * 0.55 + actionability * 0.45, 1.0)

    if lifecycle in {LevelLifecycle.BROKEN_DOWN, LevelLifecycle.REJECTED} and pivot.kind == "LOW":
        direction = "UP"
    elif lifecycle in {LevelLifecycle.BROKEN_UP, LevelLifecycle.TESTED, LevelLifecycle.RECLAIMED} and pivot.kind == "HIGH":
        direction = "DOWN"
    else:
        direction = "DOWN" if pivot.kind == "LOW" else "UP"

    return TechnicalLevel(
        value=pivot.price,
        source=f"SWING_{pivot.kind}",
        role=role,
        lifecycle_state=lifecycle,
        direction=direction,
        distance_pct=distance_pct,
        distance_atr=distance_atr,
        age_bars=age,
        tests=tests,
        broken=ever_broken or current_broken,
        reclaimed=lifecycle == LevelLifecycle.RECLAIMED,
        level_class=level_class,
        priority=priority,
        actionability=actionability,
        confidence=confidence,
        first_break_index=first_break,
        last_transition_index=history["last_transition"],
        metadata={
            "pivot_index": pivot.index,
            "pivot_degree": pivot.degree,
            "pivot_confirmed_index": pivot.confirmed_index,
            "lifecycle_events": history["events"],
            "post_break_test_count": len(history["post_break_touches"]),
        },
    )


def build_structure_state(data: pd.DataFrame) -> dict[str, Any]:
    pivots = assign_pivot_degrees(detect_confirmed_pivots(data))
    structure = classify_structure(pivots)
    events = detect_structure_events(data, pivots)
    price = float(data["Close"].iloc[-1])
    levels = [swing_level_from_pivot(item, price, len(data) - 1, data=data) for item in pivots[-12:]]
    if structure.get("last_low"):
        last_low: Pivot = structure["last_low"]
        structure["last_low_broken"] = any(
            item.source == "SWING_LOW"
            and item.metadata.get("pivot_index") == last_low.index
            and item.lifecycle_state in {LevelLifecycle.BROKEN_DOWN, LevelLifecycle.REJECTED}
            for item in levels
        )
    if structure.get("last_high"):
        last_high: Pivot = structure["last_high"]
        structure["last_high_broken"] = any(
            item.source == "SWING_HIGH"
            and item.metadata.get("pivot_index") == last_high.index
            and item.lifecycle_state in {LevelLifecycle.BROKEN_UP, LevelLifecycle.TESTED, LevelLifecycle.RECLAIMED}
            for item in levels
        )
    structure.update({"pivots": pivots, "events": events, "levels": levels})
    return structure
