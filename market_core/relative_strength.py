from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _safe_return(series: pd.Series, periods: int) -> float | None:
    if len(series) <= periods:
        return None
    start = float(series.iloc[-1 - periods])
    end = float(series.iloc[-1])
    if not math.isfinite(start) or not math.isfinite(end) or start == 0:
        return None
    return (end / start - 1.0) * 100.0


def build_relative_strength(
    stock_data: pd.DataFrame,
    benchmark_data: pd.DataFrame | None,
    *,
    benchmark_name: str = "BENCHMARK",
) -> dict[str, Any]:
    """Hisseyi benchmark ile aynı tarihlerde karşılaştırır.

    Göreceli güç fon akışı değildir; yalnız eş zamanlı relatif performanstır.
    """
    if benchmark_data is None or "Close" not in benchmark_data.columns:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "benchmark": benchmark_name,
            "reason": "Benchmark verisi sağlanmadı.",
        }
    joined = pd.concat(
        [stock_data["Close"].rename("stock"), benchmark_data["Close"].rename("benchmark")],
        axis=1,
        join="inner",
    ).dropna()
    if len(joined) < 6:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "benchmark": benchmark_name,
            "reason": "Eşleşen benchmark bar sayısı yetersiz.",
        }

    periods: dict[str, dict[str, float | None]] = {}
    valid_excess: list[float] = []
    for period in (5, 20, 60):
        stock_return = _safe_return(joined["stock"], period)
        benchmark_return = _safe_return(joined["benchmark"], period)
        excess = None if stock_return is None or benchmark_return is None else stock_return - benchmark_return
        periods[str(period)] = {
            "stock_return_pct": stock_return,
            "benchmark_return_pct": benchmark_return,
            "excess_return_pct": excess,
        }
        if excess is not None:
            valid_excess.append(excess)

    ratio = joined["stock"] / joined["benchmark"].replace(0, pd.NA)
    ratio = ratio.dropna()
    ratio_slope_5 = None
    if len(ratio) >= 6 and float(ratio.iloc[-6]) != 0:
        ratio_slope_5 = (float(ratio.iloc[-1]) / float(ratio.iloc[-6]) - 1.0) * 100.0

    excess20 = periods["20"]["excess_return_pct"]
    if excess20 is not None and excess20 > 2.0 and (ratio_slope_5 is None or ratio_slope_5 > 0):
        state = "OUTPERFORMING"
        direction = "BULLISH"
    elif excess20 is not None and excess20 < -2.0 and (ratio_slope_5 is None or ratio_slope_5 < 0):
        state = "UNDERPERFORMING"
        direction = "BEARISH"
    elif excess20 is None:
        state = "INSUFFICIENT"
        direction = "UNCERTAINTY"
    else:
        state = "MIXED"
        direction = "NEUTRAL"

    consistency = 0.0
    if valid_excess:
        positives = sum(value > 0 for value in valid_excess)
        negatives = sum(value < 0 for value in valid_excess)
        consistency = max(positives, negatives) / len(valid_excess)

    return {
        "available": True,
        "state": state,
        "direction": direction,
        "benchmark": benchmark_name,
        "periods": periods,
        "ratio_slope_5_pct": ratio_slope_5,
        "consistency": consistency,
        "reason": "Relatif performans ölçümüdür; fon akışı veya emir sinyali değildir.",
    }
