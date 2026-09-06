"""Pine-faithful trend/momentum research context from the user's v6.4.x engine.

The source script's 100-point framework is preserved as *context*, not as an
AL/SAT system. It explains trend, momentum, participation, strength, price
location, entry-distance and volatility/risk conditions while keeping the repo's
existing policy of not publishing automatic trade calls.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src.original_indicators import rsi as tv_rsi
from src.original_indicators import tv_ema, tv_rma, true_range


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _dmi(frame: pd.DataFrame, length: int = 14, smooth: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    high = pd.to_numeric(frame["High"], errors="coerce").astype(float)
    low = pd.to_numeric(frame["Low"], errors="coerce").astype(float)
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=frame.index, dtype=float)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=frame.index, dtype=float)
    tr_rma = tv_rma(true_range(frame), length)
    plus = 100.0 * tv_rma(plus_dm, length) / tr_rma.replace(0.0, np.nan)
    minus = 100.0 * tv_rma(minus_dm, length) / tr_rma.replace(0.0, np.nan)
    dx = 100.0 * (plus - minus).abs() / (plus + minus).replace(0.0, np.nan)
    return plus, minus, tv_rma(dx, smooth)


def _slope_pct(series: pd.Series, lookback: int) -> float | None:
    if len(series) <= lookback:
        return None
    now = _finite(series.iloc[-1])
    then = _finite(series.iloc[-1 - lookback])
    if now is None or then in (None, 0.0):
        return None
    return (now / then - 1.0) * 100.0


def _poc_segment_overlap(row_lo: float, row_hi: float, seg_lo: float, seg_hi: float) -> float:
    return max(min(row_hi, seg_hi) - max(row_lo, seg_lo), 0.0)


def volume_profile_poc(frame: pd.DataFrame, bars: int, rows: int = 28) -> float | None:
    """Source-faithful body/wick distributed POC, not HLC3 volume bucketing."""
    window = frame.tail(bars)
    if len(window) < min(25, bars) or rows <= 0:
        return None
    top = float(pd.to_numeric(window["High"], errors="coerce").max())
    bottom = float(pd.to_numeric(window["Low"], errors="coerce").min())
    price_range = top - bottom
    if not math.isfinite(price_range) or price_range <= 0:
        return None
    step = price_range / rows
    volumes = np.zeros(rows, dtype=float)
    for _, bar in window.iterrows():
        open_price = float(bar["Open"])
        close = float(bar["Close"])
        high = float(bar["High"])
        low = float(bar["Low"])
        volume = float(bar["Volume"])
        if not all(math.isfinite(value) for value in (open_price, close, high, low, volume)) or volume <= 0:
            continue
        body_top = max(open_price, close)
        body_bottom = min(open_price, close)
        top_wick = max(high - body_top, 0.0)
        bottom_wick = max(body_bottom - low, 0.0)
        body = max(body_top - body_bottom, 0.0)
        denominator = body + 2.0 * top_wick + 2.0 * bottom_wick
        body_volume = volume * body / denominator if denominator > 0 else volume
        top_volume = volume * (2.0 * top_wick) / denominator if denominator > 0 else 0.0
        bottom_volume = volume * (2.0 * bottom_wick) / denominator if denominator > 0 else 0.0
        for row in range(rows):
            row_lo = bottom + step * row
            row_hi = row_lo + step
            added = 0.0
            if body > 0:
                added += body_volume * _poc_segment_overlap(row_lo, row_hi, body_bottom, body_top) / body
            elif row_lo <= close < row_hi:
                added += body_volume
            if top_wick > 0:
                added += top_volume * _poc_segment_overlap(row_lo, row_hi, body_top, high) / top_wick
            if bottom_wick > 0:
                added += bottom_volume * _poc_segment_overlap(row_lo, row_hi, low, body_bottom) / bottom_wick
            volumes[row] += added
    if not np.any(volumes > 0):
        return None
    index = int(np.argmax(volumes))
    return float(bottom + step * (index + 0.5))


def build_trend_momentum_context(frame: pd.DataFrame) -> dict[str, Any]:
    if len(frame) < 252:
        return {"ready": False, "reason": "En az 252 günlük tarihçe gerekli."}
    close = pd.to_numeric(frame["Close"], errors="coerce").astype(float)
    high = pd.to_numeric(frame["High"], errors="coerce").astype(float)
    low = pd.to_numeric(frame["Low"], errors="coerce").astype(float)
    open_price = pd.to_numeric(frame["Open"], errors="coerce").astype(float)
    volume = pd.to_numeric(frame["Volume"], errors="coerce").astype(float)

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    ema5 = tv_ema(close, 5)
    ema8 = tv_ema(close, 8)
    ema13 = tv_ema(close, 13)
    macd = tv_ema(close, 12) - tv_ema(close, 26)
    macd_signal = tv_ema(macd, 9)
    histogram = macd - macd_signal
    rsi = tv_rsi(frame, 14)
    plus_di, minus_di, adx = _dmi(frame, 14, 14)
    atr = tv_rma(true_range(frame), 14)

    price = float(close.iloc[-1])
    atr_now = _finite(atr.iloc[-1])
    rsi_now = _finite(rsi.iloc[-1])
    macd_now = _finite(macd.iloc[-1])
    signal_now = _finite(macd_signal.iloc[-1])
    hist_now = _finite(histogram.iloc[-1])
    hist_prev = _finite(histogram.iloc[-2])
    plus_now = _finite(plus_di.iloc[-1])
    minus_now = _finite(minus_di.iloc[-1])
    adx_now = _finite(adx.iloc[-1])

    slope20 = _slope_pct(sma20, 5)
    slope50 = _slope_pct(sma50, 10)
    slope200 = _slope_pct(sma200, 20)
    sma20_now = _finite(sma20.iloc[-1])
    sma50_now = _finite(sma50.iloc[-1])
    sma200_now = _finite(sma200.iloc[-1])
    trend_flags = {
        "price_above_sma20": sma20_now is not None and price > sma20_now,
        "sma20_above_sma50": sma20_now is not None and sma50_now is not None and sma20_now > sma50_now,
        "sma50_above_sma200": sma50_now is not None and sma200_now is not None and sma50_now > sma200_now,
        "slope20_ok": slope20 is not None and slope20 >= 0.0,
        "slope50_ok": slope50 is not None and slope50 >= 0.0,
        "slope200_ok": slope200 is not None and slope200 >= -0.5,
    }
    trend_core = all(trend_flags.values())

    ema5_now, ema8_now, ema13_now = map(_finite, (ema5.iloc[-1], ema8.iloc[-1], ema13.iloc[-1]))
    short_aligned = None not in (ema5_now, ema8_now, ema13_now) and ema5_now > ema8_now > ema13_now
    short_bear = None not in (ema5_now, ema8_now, ema13_now) and ema5_now < ema8_now < ema13_now
    short_slopes_up = bool(ema5.iloc[-1] > ema5.iloc[-2] and ema8.iloc[-1] > ema8.iloc[-2] and ema13.iloc[-1] > ema13.iloc[-2])
    short_core = bool(short_aligned and short_slopes_up)
    short_recovery = bool(
        (ema5.iloc[-1] > ema8.iloc[-1] and ema5.iloc[-2] <= ema8.iloc[-2])
        or (ema5.iloc[-1] > ema8.iloc[-1] and ema5.iloc[-1] > ema5.iloc[-2] and ema8.iloc[-1] > ema8.iloc[-2])
    )

    macd_above_signal = macd_now is not None and signal_now is not None and macd_now > signal_now
    macd_above_zero = macd_now is not None and macd_now > 0
    hist_positive = hist_now is not None and hist_now > 0
    hist_negative = hist_now is not None and hist_now < 0
    hist_rising = hist_now is not None and hist_prev is not None and hist_now > hist_prev
    hist_falling = hist_now is not None and hist_prev is not None and hist_now < hist_prev
    hist_cross_up = hist_now is not None and hist_prev is not None and hist_now > 0 >= hist_prev
    hist_cross_down = hist_now is not None and hist_prev is not None and hist_now < 0 <= hist_prev
    if hist_cross_up:
        hist_regime = "POZİTİFE GEÇİŞ"
    elif hist_cross_down:
        hist_regime = "NEGATİFE GEÇİŞ"
    elif hist_positive and hist_rising:
        hist_regime = "POZİTİF - GÜÇLENİYOR"
    elif hist_positive and hist_falling:
        hist_regime = "POZİTİF - ZAYIFLIYOR"
    elif hist_negative and hist_rising:
        hist_regime = "NEGATİF - TOPARLANIYOR"
    elif hist_negative and hist_falling:
        hist_regime = "NEGATİF - GÜÇLENİYOR"
    else:
        hist_regime = "NÖTR"

    avg_volume = _finite(volume.iloc[-11:-1].mean())
    rvol = price * 0 + (float(volume.iloc[-1]) / avg_volume if avg_volume and avg_volume > 0 else math.nan)
    turnover = close * volume
    avg_turnover = _finite(turnover.iloc[-21:-1].mean())
    relative_turnover = float(turnover.iloc[-1]) / avg_turnover if avg_turnover and avg_turnover > 0 else None

    high52 = float(high.tail(252).max())
    high20 = float(high.tail(20).max())
    previous20 = float(high.iloc[-21:-1].max())
    pct52 = price / high52 * 100.0 if high52 > 0 else None
    pct20 = price / high20 * 100.0 if high20 > 0 else None
    near52 = pct52 is not None and pct52 >= 85.0
    near20 = pct20 is not None and pct20 >= 95.0
    breakout20 = price > previous20
    required_rvol = max(1.2, 1.5) if breakout20 else 1.2
    rvol_ok = math.isfinite(rvol) and rvol > required_rvol
    participation_strong = math.isfinite(rvol) and rvol >= max(required_rvol, 1.5) and relative_turnover is not None and relative_turnover >= 1.0

    dist_sma20_pct = (price / sma20_now - 1.0) * 100.0 if sma20_now else None
    dist_sma20_atr = (price - sma20_now) / atr_now if sma20_now is not None and atr_now and atr_now > 0 else None
    distance_core = (
        dist_sma20_pct is not None
        and 0 <= dist_sma20_pct <= 7.0
        and dist_sma20_atr is not None
        and 0 <= dist_sma20_atr <= 1.5
    )

    atr_pct = atr_now / price * 100.0 if atr_now and price else None
    atr_pct_ok = atr_pct is not None and 1.5 <= atr_pct <= 7.0
    bb_mid = close.rolling(20).mean()
    bb_dev = close.rolling(20).std(ddof=0) * 2.0
    bb_width = (2.0 * bb_dev / bb_mid.replace(0.0, np.nan)) * 100.0
    bb_width_now = _finite(bb_width.iloc[-1])
    bb_width_prev = _finite(bb_width.iloc[-2])
    bb_width_avg = _finite(bb_width.tail(20).mean())
    bb_rising = bb_width_now is not None and bb_width_prev is not None and bb_width_now > bb_width_prev
    bb_above_avg = bb_width_now is not None and bb_width_avg is not None and bb_width_now > bb_width_avg

    candle_range = float(high.iloc[-1] - low.iloc[-1])
    clv = (price - float(low.iloc[-1])) / candle_range if candle_range > 0 else 0.5
    upper_wick = float(high.iloc[-1] - max(open_price.iloc[-1], close.iloc[-1]))
    upper_wick_atr = upper_wick / atr_now if atr_now and atr_now > 0 else None
    day_change = (price / float(close.iloc[-2]) - 1.0) * 100.0 if close.iloc[-2] else None
    gap = (float(open_price.iloc[-1]) / float(close.iloc[-2]) - 1.0) * 100.0 if close.iloc[-2] else None
    risk_warning = bool(
        (day_change is not None and day_change > 10.0)
        or (gap is not None and abs(gap) > 5.0)
        or not atr_pct_ok
    )

    ema_distances = {
        "ema5_pct": (price / ema5_now - 1.0) * 100.0 if ema5_now else None,
        "ema8_pct": (price / ema8_now - 1.0) * 100.0 if ema8_now else None,
        "ema13_pct": (price / ema13_now - 1.0) * 100.0 if ema13_now else None,
    }
    warn_thresholds = {"ema5_pct": 2.5, "ema8_pct": 3.5, "ema13_pct": 5.0}
    high_thresholds = {"ema5_pct": 4.5, "ema8_pct": 6.0, "ema13_pct": 7.5}
    warn_count = sum(ema_distances[key] is not None and ema_distances[key] >= warn_thresholds[key] for key in ema_distances)
    high_count = sum(ema_distances[key] is not None and ema_distances[key] >= high_thresholds[key] for key in ema_distances)
    ema_short_count = sum(price > value for value in (ema5_now, ema8_now, ema13_now) if value is not None)
    mean_reversion_high = ema_short_count == 3 and (high_count >= 2 or warn_count == 3)
    mean_reversion_warn = ema_short_count >= 2 and not mean_reversion_high and (high_count >= 1 or warn_count >= 2)

    prior_dist = (close - sma20) / atr.replace(0.0, np.nan)
    was_above_sma20 = _finite(prior_dist.iloc[-11:-1].max()) is not None and float(prior_dist.iloc[-11:-1].max()) >= 0.75
    touched = bool(
        atr_now
        and sma20_now is not None
        and float(low.iloc[-1]) <= sma20_now + 0.25 * atr_now
        and float(low.iloc[-1]) >= sma20_now - 0.50 * atr_now
    )
    pullback_setup = bool(
        not breakout20
        and was_above_sma20
        and touched
        and sma20_now is not None
        and price > sma20_now
        and dist_sma20_atr is not None
        and dist_sma20_atr <= 1.0
        and (price > float(open_price.iloc[-1]) or clv >= 0.60)
    )
    rsi_trend_ok = rsi_now is not None and 55.0 <= rsi_now <= 72.0
    rsi_pullback_ok = rsi_now is not None and 50.0 <= rsi_now <= 72.0
    hist_bull_strengthening = bool(hist_positive and hist_rising)
    hist_bear_recovering = bool(hist_negative and hist_rising)
    pullback_momentum_ok = bool(macd_above_zero and rsi_pullback_ok and (hist_bear_recovering or hist_cross_up or hist_bull_strengthening))
    breakout_momentum_ok = bool(macd_above_signal and macd_above_zero and rsi_trend_ok and (hist_bull_strengthening or hist_cross_up))
    breakout_quality_ok = bool(bb_rising and clv >= 0.60 and (upper_wick_atr is None or upper_wick_atr <= 0.50))

    trend_score = (
        (4 if trend_flags["price_above_sma20"] else 0)
        + (4 if trend_flags["sma20_above_sma50"] else 0)
        + (4 if trend_flags["sma50_above_sma200"] else 0)
        + (3 if trend_flags["slope20_ok"] else 0)
        + (3 if trend_flags["slope50_ok"] else 0)
        + (2 if slope200 is not None and slope200 > 0 else 0)
        + (3 if short_aligned else 0)
        + (2 if short_slopes_up else 0)
    )
    hist_score = 6 if hist_cross_up or hist_bull_strengthening else 4 if hist_bear_recovering else 2 if hist_positive and hist_falling else 0
    momentum_score = (4 if macd_above_zero else 0) + (5 if macd_above_signal else 0) + hist_score + (5 if rsi_now is not None and 55 <= rsi_now <= 68 else 0)
    if math.isfinite(rvol):
        rvol_score = 18 if rvol >= 3 else 16 if rvol >= 2 else 12 if rvol >= 1.5 else 7 if rvol >= 1.2 else 3 if rvol >= 1 else 0
    else:
        rvol_score = 0
    volume_score = rvol_score + (2 if relative_turnover is not None and relative_turnover >= 1.0 else 0)
    adx_score = 7 if adx_now is not None and adx_now >= 40 else 6 if adx_now is not None and adx_now >= 30 else 5 if adx_now is not None and adx_now >= 25 else 3 if adx_now is not None and adx_now > 20 else 0
    di_ok = plus_now is not None and minus_now is not None and plus_now > minus_now
    strength_score = adx_score + (3 if di_ok else 0)
    location_score = (7 if pct52 is not None and pct52 >= 95 else 5 if pct52 is not None and pct52 >= 90 else 3 if near52 else 0) + (3 if near20 else 0)
    dist_pct_score = 5 if dist_sma20_pct is not None and 0 <= dist_sma20_pct <= 3 else 4 if dist_sma20_pct is not None and 3 < dist_sma20_pct <= 5 else 2 if dist_sma20_pct is not None and 5 < dist_sma20_pct <= 7 else 0
    dist_atr_score = 5 if dist_sma20_atr is not None and 0 <= dist_sma20_atr < 1 else 4 if dist_sma20_atr is not None and 1 <= dist_sma20_atr <= 1.5 else 2 if dist_sma20_atr is not None and 1.5 < dist_sma20_atr <= 2 else 0
    entry_score = dist_pct_score + dist_atr_score
    volatility_score = (2 if bb_rising else 0) + (1 if bb_above_avg else 0) + (2 if atr_pct_ok else 0)
    total_score = trend_score + momentum_score + volume_score + strength_score + location_score + entry_score + volatility_score
    quality = "A+" if total_score >= 85 else "A" if total_score >= 80 else "B+" if total_score >= 75 else "B" if total_score >= 70 else "İZLEME" if total_score >= 60 else "ZAYIF"

    structure_core = bool(trend_core and adx_now is not None and adx_now > 20 and di_ok and near52)
    common = bool(structure_core and rvol_ok and distance_core and total_score >= 75)
    if common and breakout20 and short_core and breakout_momentum_ok and breakout_quality_ok:
        setup = "BREAKOUT ADAYI"
    elif structure_core and rvol_ok and distance_core and total_score >= 75 and pullback_setup and pullback_momentum_ok and (short_recovery or short_core):
        setup = "PULLBACK ADAYI"
    elif common and not breakout20 and not pullback_setup and short_core and macd_above_signal and macd_above_zero and rsi_trend_ok and (hist_bull_strengthening or hist_cross_up):
        setup = "TREND DEVAMI ADAYI"
    elif structure_core and rvol_ok and not distance_core and macd_above_signal and macd_above_zero and hist_positive and rsi_now is not None and rsi_now >= 55 and total_score >= 60:
        setup = "GÜÇLÜ AMA UZAMIŞ"
    elif total_score >= 60:
        setup = "İZLEME"
    else:
        setup = "ZAYIF / TEYİTSİZ"

    return {
        "ready": True,
        "score": total_score,
        "quality": quality,
        "setup": setup,
        "trend_core": trend_core,
        "trend_flags": trend_flags,
        "sma_slopes_pct": {"sma20": slope20, "sma50": slope50, "sma200": slope200},
        "short_trend": {"bull_aligned": short_aligned, "bear_aligned": short_bear, "slopes_up": short_slopes_up, "recovery": short_recovery},
        "momentum": {"hist_regime": hist_regime, "macd_above_signal": macd_above_signal, "macd_above_zero": macd_above_zero, "rsi": rsi_now},
        "strength": {"adx": adx_now, "plus_di": plus_now, "minus_di": minus_now, "di_ok": di_ok},
        "participation": {"rvol10": rvol if math.isfinite(rvol) else None, "relative_turnover20": relative_turnover, "strong": participation_strong},
        "location": {"pct_52w_high": pct52, "pct_20d_high": pct20, "breakout20": breakout20, "near52": near52, "near20": near20},
        "distance": {"sma20_pct": dist_sma20_pct, "sma20_atr": dist_sma20_atr, "acceptable": distance_core},
        "ema_stretch": {**ema_distances, "warn_count": warn_count, "high_count": high_count, "warning": mean_reversion_warn, "high_risk": mean_reversion_high},
        "candle_quality": {"clv": clv, "upper_wick_atr": upper_wick_atr},
        "volatility": {"atr_pct": atr_pct, "atr_pct_ok": atr_pct_ok, "bb_width": bb_width_now, "bb_width_rising": bb_rising, "bb_width_above_avg": bb_above_avg},
        "risk": {"day_change_pct": day_change, "gap_pct": gap, "warning": risk_warning},
        "setup_evidence": {"pullback_setup": pullback_setup, "pullback_momentum_ok": pullback_momentum_ok, "breakout_momentum_ok": breakout_momentum_ok, "breakout_quality_ok": breakout_quality_ok},
        "score_components": {"trend": trend_score, "momentum": momentum_score, "participation": volume_score, "strength": strength_score, "location": location_score, "entry_distance": entry_score, "volatility": volatility_score},
        "poc": {"short": volume_profile_poc(frame, 60, 28), "medium": volume_profile_poc(frame, 140, 28), "long": volume_profile_poc(frame, 260, 28)},
    }
