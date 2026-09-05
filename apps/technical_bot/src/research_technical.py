"""Technical research layer driven by the same original indicators as the chart."""

from __future__ import annotations

from typing import Any

from src import research_engine as core
from src.original_indicators import build_indicator_frame
from src.research_engine import LevelZone


def _technical_analysis(symbol: str) -> tuple[dict[str, Any], tuple[LevelZone, ...], tuple[LevelZone, ...]]:
    import borsapy as bp

    stock = bp.Ticker(symbol)
    prepared = core._prepare_prices(stock.history(period="2y", interval="1d"))
    daily, divergences = build_indicator_frame(prepared, include_hidden_divergence=False)
    daily = daily.dropna(subset=["ATR14"]).copy()
    # The longest visual MA (233) is optional and may legitimately be unavailable
    # for recently listed shares. Core technical indicators only need a much
    # shorter history, so fail closed only when market-structure context itself
    # would be unreliable.
    if len(daily) < 80:
        raise RuntimeError("Insufficient daily history for technical research")

    pivot_frame = prepared.dropna(subset=["ATR"])
    pivots = core._pivots(pivot_frame)
    structure = core._structure(pivot_frame, pivots)
    supports, resistances = core._level_zones(pivot_frame, pivots)
    row = daily.iloc[-1]
    price = float(row["Close"])

    structure_score = 85.0 if structure["state"] == "HH / HL" else 15.0 if structure["state"] == "LH / LL" else 50.0

    alpha = core._finite(row.get("AlphaTrend"))
    alpha_lag2 = core._finite(row.get("AlphaTrendLag2"))
    if alpha is None or alpha_lag2 is None:
        alpha_score = None
        alpha_state = "VERİ YETERSİZ"
    elif price > alpha > alpha_lag2:
        alpha_score = 90.0
        alpha_state = "FİYAT ÜSTÜNDE / YÜKSELEN"
    elif price < alpha < alpha_lag2:
        alpha_score = 10.0
        alpha_state = "FİYAT ALTINDA / DÜŞEN"
    else:
        alpha_score = 50.0
        alpha_state = "KARIŞIK"

    rsi_value = core._finite(row.get("RSI14"))
    macd_hist = core._finite(row.get("MACD_HIST"))
    smi_value = core._finite(row.get("SMI"))
    smi_signal = core._finite(row.get("SMI_SIGNAL"))
    obv_series = daily["OBV"].dropna()
    obv_change = None
    if len(obv_series) >= 11 and abs(float(obv_series.iloc[-11])) > 1e-9:
        old_obv = float(obv_series.iloc[-11])
        new_obv = float(obv_series.iloc[-1])
        obv_change = (new_obv - old_obv) / abs(old_obv) * 100.0

    smi_score = None
    if smi_value is not None and smi_signal is not None:
        if smi_value > smi_signal and smi_value > 0:
            smi_score = 85.0
        elif smi_value < smi_signal and smi_value < 0:
            smi_score = 15.0
        else:
            smi_score = 50.0

    momentum_score, momentum_cov = core._weighted(
        [
            (core._score_target(rsi_value, 50.0, 68.0, 25.0, 85.0), 1.0),
            (core._score_higher(macd_hist, -abs(price) * 0.01, abs(price) * 0.01), 1.0),
            (smi_score, 1.0),
            (core._score_higher(obv_change, -10.0, 10.0), 0.7),
        ]
    )

    weekly_prepared = core._prepare_prices(
        prepared[["Open", "High", "Low", "Close", "Volume"]]
        .resample("W-FRI")
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
    weekly_pivots = core._pivots(weekly_prepared, left=2, right=2)
    weekly_structure = core._structure(weekly_prepared, weekly_pivots) if weekly_pivots else {"state": "—", "bos": "—"}
    weekly_score = 80.0 if weekly_structure["state"] == "HH / HL" else 20.0 if weekly_structure["state"] == "LH / LL" else 50.0

    technical_score, technical_cov = core._weighted(
        [
            (structure_score, 1.3),
            (alpha_score, 1.1),
            (momentum_score, 1.2),
            (weekly_score, 1.0),
        ]
    )

    atr_value = core._finite(row.get("ATR14"))
    atr_pct = atr_value / price * 100.0 if atr_value is not None and price else None
    turnover = (daily["Close"] * daily["Volume"]).tail(20)
    avg_turnover = core._finite(turnover.mean())
    volume_mean = core._finite(daily["Volume"].iloc[-21:-1].mean())
    rvol = core._ratio(core._finite(row.get("Volume")), volume_mean)
    latest_divergence = None
    visible_divergences = [point for point in divergences if point.index >= daily.index[-60]]
    if visible_divergences:
        latest = visible_divergences[-1]
        latest_divergence = {"kind": latest.kind, "time": str(latest.index), "rsi": latest.rsi, "price": latest.price}

    bb_upper = core._finite(row.get("BB_UPPER"))
    bb_lower = core._finite(row.get("BB_LOWER"))
    bb_mid = core._finite(row.get("BB_MID"))
    if bb_upper is not None and price > bb_upper:
        bb_state = "ÜST BAND ÜZERİ"
    elif bb_lower is not None and price < bb_lower:
        bb_state = "ALT BAND ALTI"
    elif bb_mid is not None and price >= bb_mid:
        bb_state = "ORTA BAND ÜSTÜ"
    elif bb_mid is not None:
        bb_state = "ORTA BAND ALTI"
    else:
        bb_state = "VERİ YETERSİZ"

    return (
        {
            "score": technical_score,
            "coverage": technical_cov,
            "label": core._label(technical_score, "POZİTİF", "KARIŞIK", "ZAYIF"),
            "structure": structure,
            "weekly_structure": weekly_structure,
            "rsi14": rsi_value,
            "macd_hist": macd_hist,
            "smi": smi_value,
            "smi_signal": smi_signal,
            "obv_10d_change": obv_change,
            "alpha_trend": alpha,
            "alpha_trend_lag2": alpha_lag2,
            "alpha_trend_state": alpha_state,
            "bollinger_state": bb_state,
            "latest_rsi_divergence": latest_divergence,
            "momentum_score": momentum_score,
            "momentum_coverage": momentum_cov,
            "atr": atr_value,
            "atr_pct": atr_pct,
            "rvol20": rvol,
            "average_turnover_20": avg_turnover,
            "pivots": pivots[-12:],
        },
        supports,
        resistances,
    )
