from __future__ import annotations

import itertools
from typing import Any

import numpy as np
import pandas as pd

INDICATORS = {"RSI": "RSI", "MACD": "MACD", "SMI": "SMI"}


def _pivot_positions(series: pd.Series, left: int, right: int, low: bool) -> list[int]:
    values = series.to_numpy(dtype=float)
    positions: list[int] = []
    for position in range(left, len(values) - right):
        window = values[position - left : position + right + 1]
        if not np.isfinite(window).all():
            continue
        neighbours = np.concatenate((window[:left], window[left + 1 :]))
        is_pivot = values[position] < np.min(neighbours) if low else values[position] > np.max(neighbours)
        if is_pivot:
            positions.append(position)
    return positions


def _event(
    data: pd.DataFrame,
    indicator: str,
    oscillator: pd.Series,
    first: int,
    second: int,
    right: int,
    bullish: bool,
) -> dict[str, Any]:
    confirmation_position = second + right
    price_column = "Low" if bullish else "High"
    tone = "positive" if bullish else "negative"
    direction = "Pozitif normal uyumsuzluk" if bullish else "Negatif normal uyumsuzluk"
    return {
        "indicator": indicator,
        "event": f"{indicator} {direction}",
        "state": direction,
        "tone": tone,
        "bullish": bullish,
        "pivot_relation": "LL / HL" if bullish else "HH / LH",
        "first_pivot_time": data.index[first].isoformat(),
        "second_pivot_time": data.index[second].isoformat(),
        "confirmation_time": data.index[confirmation_position].isoformat(),
        "event_age": len(data) - 1 - confirmation_position,
        "price_first": float(data[price_column].iloc[first]),
        "price_second": float(data[price_column].iloc[second]),
        "oscillator_first": float(oscillator.iloc[first]),
        "oscillator_second": float(oscillator.iloc[second]),
    }


def detect_divergences(
    data: pd.DataFrame,
    left: int = 5,
    right: int = 5,
    range_lower: int = 5,
    range_upper: int = 60,
    max_event_age: int = 60,
) -> dict[str, Any]:
    """TradingView RSI örneğindeki regular divergence mantığını uygular.

    Pivotlar osilatörde bulunur. Pozitif uyumsuzlukta osilatör HL ve aynı
    pivot barlarındaki fiyat Low serisi LL; negatifte osilatör LH ve fiyat
    High serisi HH yapmalıdır. Sağ pivot barları tamamlanmadan olay teyitli
    sayılmaz.
    """
    indicators: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = []
    required = {"Low", "High", *INDICATORS.values()}
    if len(data) < left + right + range_lower + 1 or not required.issubset(data.columns):
        for name in INDICATORS:
            indicators[name] = {
                "detected": False,
                "state": "Yetersiz veri",
                "tone": "neutral",
                "event_age": None,
            }
        return {"indicators": indicators, "events": events, "settings": _settings(left, right, range_lower, range_upper, max_event_age)}

    for name, column in INDICATORS.items():
        oscillator = data[column]
        candidates: list[dict[str, Any]] = []
        low_pivots = _pivot_positions(oscillator, left, right, low=True)
        high_pivots = _pivot_positions(oscillator, left, right, low=False)
        for first, second in itertools.pairwise(low_pivots):
            distance = second - first
            if not range_lower <= distance <= range_upper:
                continue
            oscillator_higher_low = float(oscillator.iloc[second]) > float(oscillator.iloc[first])
            price_lower_low = float(data["Low"].iloc[second]) < float(data["Low"].iloc[first])
            if oscillator_higher_low and price_lower_low:
                candidates.append(_event(data, name, oscillator, first, second, right, bullish=True))
        for first, second in itertools.pairwise(high_pivots):
            distance = second - first
            if not range_lower <= distance <= range_upper:
                continue
            oscillator_lower_high = float(oscillator.iloc[second]) < float(oscillator.iloc[first])
            price_higher_high = float(data["High"].iloc[second]) > float(data["High"].iloc[first])
            if oscillator_lower_high and price_higher_high:
                candidates.append(_event(data, name, oscillator, first, second, right, bullish=False))
        recent = [item for item in candidates if 0 <= int(item["event_age"]) <= max_event_age]
        if recent:
            latest = min(recent, key=lambda item: int(item["event_age"]))
            indicators[name] = {"detected": True, **latest}
            events.extend(recent)
        else:
            indicators[name] = {
                "detected": False,
                "state": f"Son {max_event_age} barda yok",
                "tone": "neutral",
                "event_age": None,
            }

    events.sort(key=lambda item: int(item["event_age"]))
    return {
        "indicators": indicators,
        "events": events,
        "settings": _settings(left, right, range_lower, range_upper, max_event_age),
        "method": "TradingView RSI regular divergence semantiği; pivotlar osilatörde 5/5 ile teyit edilir, fiyat aynı pivot barlarından karşılaştırılır.",
    }


def _settings(left: int, right: int, range_lower: int, range_upper: int, max_event_age: int) -> dict[str, int]:
    return {
        "lookback_left": left,
        "lookback_right": right,
        "range_lower": range_lower,
        "range_upper": range_upper,
        "max_event_age": max_event_age,
    }
