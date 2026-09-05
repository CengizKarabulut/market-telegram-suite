"""Technical research layer driven by the same original indicators as the chart.

This layer keeps price structure primary. Indicator families are confirmation,
not independent buy/sell votes. Multi-timeframe context is derived from closed
higher-timeframe bars built from the same daily history, and Elliott context is
intentionally conservative: it may stay uncertain instead of forcing a count.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src import research_engine as core
from src.original_indicators import build_indicator_frame
from src.research_engine import LevelZone


def _structure_score(state: str) -> float | None:
    if state == "HH / HL":
        return 85.0
    if state == "LH / LL":
        return 15.0
    if state in {"HH / LL", "LH / HL"}:
        return 50.0
    return None


def _structure_event(structure: dict[str, Any]) -> str:
    """Classify a confirmed break as continuation BOS or conservative CHoCH."""
    bos = str(structure.get("bos", ""))
    last_high = structure.get("last_high") or {}
    last_low = structure.get("last_low") or {}
    high_label = str(last_high.get("label", ""))
    low_label = str(last_low.get("label", ""))

    if "Swing High üzeri BOS" in bos:
        if high_label == "LH" or low_label == "LL":
            return "CHoCH YUKARI"
        return "BOS YUKARI"
    if "Swing Low altı BOS" in bos:
        if high_label == "HH" or low_label == "HL":
            return "CHoCH AŞAĞI"
        return "BOS AŞAĞI"
    return "YENİ KIRILIM YOK"


def _collapse_alternating(pivots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pivot in pivots:
        if not result or result[-1]["type"] != pivot["type"]:
            result.append(pivot)
            continue
        previous = result[-1]
        if (
            pivot["type"] == "high"
            and float(pivot["price"]) >= float(previous["price"])
        ) or (
            pivot["type"] == "low"
            and float(pivot["price"]) <= float(previous["price"])
        ):
            result[-1] = pivot
    return result


def _elliott_context(pivots: list[dict[str, Any]], structure: dict[str, Any]) -> dict[str, Any]:
    """Return a non-forced Elliott hypothesis with confidence and invalidation."""
    alternating = _collapse_alternating(pivots[-14:])
    state = str(structure.get("state", "—"))
    event = _structure_event(structure)
    if len(alternating) < 5:
        return {
            "primary": "BELİRSİZ",
            "alternate": "—",
            "confidence": 20,
            "invalidation": None,
            "note": "Yeterli teyitli alternatif swing yok; dalga sayımı zorlanmadı.",
        }

    highs = [item for item in alternating if item["type"] == "high"]
    lows = [item for item in alternating if item["type"] == "low"]
    if state == "HH / HL":
        invalidation = float(lows[-1]["price"]) if lows else None
        confidence = 65 if event == "BOS YUKARI" else 55
        return {
            "primary": "YÜKSELİŞ İTKİ / DÜZELTME ADAYI",
            "alternate": "ABC DÜZELTMESİ",
            "confidence": confidence,
            "invalidation": invalidation,
            "note": "Kesin 1-5 etiketi verilmez; teyitli swing dizisi ve yapı kullanılır.",
        }
    if state == "LH / LL":
        invalidation = float(highs[-1]["price"]) if highs else None
        confidence = 65 if event == "BOS AŞAĞI" else 55
        return {
            "primary": "DÜŞÜŞ İTKİ / DÜZELTME ADAYI",
            "alternate": "ABC TEPKİSİ",
            "confidence": confidence,
            "invalidation": invalidation,
            "note": "Kesin 1-5 etiketi verilmez; teyitli swing dizisi ve yapı kullanılır.",
        }
    return {
        "primary": "BELİRSİZ",
        "alternate": "YATAY / KOMPLEKS DÜZELTME",
        "confidence": 30,
        "invalidation": None,
        "note": "Karışık piyasa yapısında Elliott bağlamı karar girdisi yapılmaz.",
    }


def _resample_context(
    prepared: pd.DataFrame,
    rule: str,
    *,
    left: int,
    right: int,
) -> dict[str, Any]:
    frame = (
        prepared[["Open", "High", "Low", "Close", "Volume"]]
        .resample(rule)
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna()
    )
    if len(frame) < left + right + 8:
        return {"state": "—", "bos": "—", "event": "VERİ YETERSİZ"}
    context = core._prepare_prices(frame)
    pivots = core._pivots(context, left=left, right=right)
    structure = core._structure(context, pivots) if pivots else {"state": "—", "bos": "—"}
    return {**structure, "event": _structure_event(structure)}


def _technical_analysis(symbol: str) -> tuple[dict[str, Any], tuple[LevelZone, ...], tuple[LevelZone, ...]]:
    import borsapy as bp

    stock = bp.Ticker(symbol)
    prepared = core._prepare_prices(stock.history(period="2y", interval="1d"))
    daily, divergences = build_indicator_frame(prepared, include_hidden_divergence=False)
    daily = daily.dropna(subset=["ATR14"]).copy()
    if len(daily) < 80:
        raise RuntimeError("Insufficient daily history for technical research")

    pivot_frame = prepared.dropna(subset=["ATR"])
    pivots = core._pivots(pivot_frame)
    structure = core._structure(pivot_frame, pivots)
    structure = {**structure, "event": _structure_event(structure)}
    supports, resistances = core._level_zones(pivot_frame, pivots)
    row = daily.iloc[-1]
    price = float(row["Close"])

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

    weekly_structure = _resample_context(prepared, "W-FRI", left=2, right=2)
    monthly_structure = _resample_context(prepared, "ME", left=1, right=1)
    mtf = {
        "1G": structure,
        "1Hf": weekly_structure,
        "1A": monthly_structure,
    }
    weekly_score = _structure_score(str(weekly_structure.get("state", "—")))
    monthly_score = _structure_score(str(monthly_structure.get("state", "—")))

    technical_score, technical_cov = core._weighted(
        [
            (_structure_score(str(structure.get("state", "—"))), 1.3),
            (alpha_score, 1.1),
            (momentum_score, 1.2),
            (weekly_score, 1.0),
            (monthly_score, 0.6),
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
        latest_divergence = {
            "kind": latest.kind,
            "time": str(latest.index),
            "rsi": latest.rsi,
            "price": latest.price,
        }

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
            "monthly_structure": monthly_structure,
            "mtf": mtf,
            "elliott": _elliott_context(pivots, structure),
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
