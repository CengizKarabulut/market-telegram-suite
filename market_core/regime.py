from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _series_last(data: pd.DataFrame, name: str) -> float | None:
    if name not in data.columns or not len(data):
        return None
    return _num(data[name].iloc[-1])


def build_regime(data: pd.DataFrame, indicators: dict[str, Any] | None = None) -> dict[str, Any]:
    """Trend/range/squeeze/expansion/geçiş rejimini deterministik sınıflar.

    Rejim AL/SAT üretmez; diğer evidence ailelerinin hangi ortamda
    değerlendirilmesi gerektiğini söyler.
    """
    indicators = dict(indicators or {})
    close = data["Close"].astype(float)
    if len(close) < 10:
        return {"state": "INSUFFICIENT", "confidence": 0.0, "reasons": ["En az 10 bar gerekir."]}

    adx = _num(indicators.get("ADX")) or _series_last(data, "ADX")
    atr = _num(indicators.get("ATR")) or _series_last(data, "ATR")
    bb_width = _num(indicators.get("BB_WIDTH")) or _series_last(data, "BB_WIDTH")
    ema20 = _num(indicators.get("EMA20")) or _series_last(data, "EMA20")
    ema50 = _num(indicators.get("EMA50")) or _series_last(data, "EMA50")

    lookback = min(20, len(close) - 1)
    net_move = abs(float(close.iloc[-1] - close.iloc[-1 - lookback]))
    path = float(close.diff().abs().iloc[-lookback:].sum())
    efficiency = net_move / path if path > 0 else 0.0

    rolling_range = float((data["High"].iloc[-lookback:].max() - data["Low"].iloc[-lookback:].min()))
    atr_ratio = rolling_range / (atr * lookback) if atr and atr > 0 else None
    price = float(close.iloc[-1])
    trend_alignment = None
    if ema20 is not None and ema50 is not None:
        if price > ema20 > ema50:
            trend_alignment = "UP"
        elif price < ema20 < ema50:
            trend_alignment = "DOWN"
        else:
            trend_alignment = "MIXED"

    reasons: list[str] = []
    if bb_width is not None and bb_width < 0.06 and (adx is None or adx < 22):
        state = "SQUEEZE"
        confidence = 0.82
        reasons.append("Bant genişliği dar ve ADX düşük; sıkışma rejimi.")
    elif adx is not None and adx >= 25 and efficiency >= 0.35 and trend_alignment in {"UP", "DOWN"}:
        state = "DIRECTIONAL_TREND_UP" if trend_alignment == "UP" else "DIRECTIONAL_TREND_DOWN"
        confidence = min(0.72 + (adx - 25) / 100 + efficiency * 0.15, 0.95)
        reasons.append(f"ADX {adx:.1f}, fiyat verimliliği {efficiency:.2f} ve EMA hizası {trend_alignment}.")
    elif efficiency < 0.22 and (adx is None or adx < 22):
        state = "RANGE"
        confidence = 0.75
        reasons.append(f"Fiyat verimliliği {efficiency:.2f}; yönsüz rotasyon baskın.")
    elif atr_ratio is not None and atr_ratio > 0.9 and (adx is None or adx < 25):
        state = "HIGH_VOL_NON_DIRECTIONAL"
        confidence = 0.7
        reasons.append("Geniş fiyat alanı var fakat yönlülük yeterince güçlü değil.")
    else:
        state = "TRANSITION"
        confidence = 0.55
        reasons.append("Trend/range/squeeze kriterlerinden hiçbiri baskın değil; geçiş rejimi.")

    return {
        "state": state,
        "confidence": confidence,
        "adx": adx,
        "efficiency": efficiency,
        "bb_width": bb_width,
        "atr_ratio": atr_ratio,
        "trend_alignment": trend_alignment,
        "reasons": reasons,
    }
