from __future__ import annotations

import math
from typing import Any

import pandas as pd


SHORT_EMA_PERIODS = (5, 8, 13)
TREND_EMA_PERIODS = (20, 50, 100, 200)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _last(data: pd.DataFrame, column: str) -> float | None:
    if column not in data.columns or data.empty:
        return None
    return _number(data[column].iloc[-1])


def _previous(data: pd.DataFrame, column: str, bars: int = 1) -> float | None:
    if column not in data.columns or len(data) <= bars:
        return None
    return _number(data[column].iloc[-1 - bars])


def _slope_pct(data: pd.DataFrame, column: str, bars: int = 3) -> float | None:
    current = _last(data, column)
    previous = _previous(data, column, bars)
    if current is None or previous is None or previous == 0:
        return None
    return (current / previous - 1.0) * 100.0 / bars


def _cross_state(data: pd.DataFrame, main: str, signal: str) -> str:
    current_main = _last(data, main)
    current_signal = _last(data, signal)
    previous_main = _previous(data, main)
    previous_signal = _previous(data, signal)
    if None in {current_main, current_signal, previous_main, previous_signal}:
        return "UNAVAILABLE"
    if current_main > current_signal and previous_main <= previous_signal:
        return "CROSS_UP"
    if current_main < current_signal and previous_main >= previous_signal:
        return "CROSS_DOWN"
    if current_main > current_signal:
        return "ABOVE"
    if current_main < current_signal:
        return "BELOW"
    return "EQUAL"


def _level_cross_state(data: pd.DataFrame, column: str, level: float) -> str:
    current = _last(data, column)
    previous = _previous(data, column)
    if current is None or previous is None:
        return "UNAVAILABLE"
    if current > level and previous <= level:
        return "CROSS_UP"
    if current < level and previous >= level:
        return "CROSS_DOWN"
    if current > level:
        return "ABOVE"
    if current < level:
        return "BELOW"
    return "EQUAL"


def _price_relation(price: float | None, value: float | None) -> str:
    if price is None or value is None:
        return "UNAVAILABLE"
    if price > value:
        return "PRICE_ABOVE"
    if price < value:
        return "PRICE_BELOW"
    return "AT_LEVEL"


def _short_ma_state(data: pd.DataFrame, price: float | None) -> dict[str, Any]:
    values: dict[str, float] = {}
    slopes: dict[str, float] = {}
    relations: dict[str, str] = {}
    for period in SHORT_EMA_PERIODS:
        column = f"EMA_{period}"
        value = _last(data, column)
        if value is None:
            continue
        values[str(period)] = value
        slope = _slope_pct(data, column)
        if slope is not None:
            slopes[str(period)] = slope
        relations[str(period)] = _price_relation(price, value)

    if len(values) < 3:
        state = "INSUFFICIENT"
        arrangement = "UNAVAILABLE"
    else:
        e5, e8, e13 = values["5"], values["8"], values["13"]
        if e5 > e8 > e13:
            arrangement = "5>8>13"
        elif e5 < e8 < e13:
            arrangement = "5<8<13"
        else:
            arrangement = "MIXED"
        all_up = len(slopes) == 3 and all(value > 0 for value in slopes.values())
        all_down = len(slopes) == 3 and all(value < 0 for value in slopes.values())
        price_above_all = all(value == "PRICE_ABOVE" for value in relations.values())
        price_below_all = all(value == "PRICE_BELOW" for value in relations.values())
        if arrangement == "5>8>13" and all_up and price_above_all:
            state = "BULLISH_ALIGNMENT"
        elif arrangement == "5<8<13" and all_down and price_below_all:
            state = "BEARISH_ALIGNMENT"
        elif arrangement == "5>8>13":
            state = "BULLISH_BUT_INCOMPLETE"
        elif arrangement == "5<8<13":
            state = "BEARISH_BUT_INCOMPLETE"
        else:
            state = "MIXED"

    if state == "BULLISH_ALIGNMENT":
        interpretation = "EMA5/8/13 pozitif sıralı, eğimler yukarı ve fiyat kısa ortalamaların üzerinde."
    elif state == "BEARISH_ALIGNMENT":
        interpretation = "EMA5/8/13 negatif sıralı, eğimler aşağı ve fiyat kısa ortalamaların altında."
    elif state == "BULLISH_BUT_INCOMPLETE":
        interpretation = "EMA5/8/13 pozitif sıralı ancak fiyat konumu veya eğimler tam teyit üretmiyor."
    elif state == "BEARISH_BUT_INCOMPLETE":
        interpretation = "EMA5/8/13 negatif sıralı ancak fiyat konumu veya eğimler tam teyit üretmiyor."
    elif state == "MIXED":
        interpretation = "EMA5/8/13 dizilimi karışık; kısa vadeli trend ortalamalarda netleşmiş değil."
    else:
        interpretation = "EMA5/8/13 değerlendirmesi için yeterli veri yok."
    return {
        "state": state,
        "arrangement": arrangement,
        "values": values,
        "slope_pct_per_bar": slopes,
        "price_relation": relations,
        "interpretation": interpretation,
    }


def _trend_state(data: pd.DataFrame, price: float | None) -> dict[str, Any]:
    short = _short_ma_state(data, price)
    averages: dict[str, dict[str, Any]] = {}
    positive = 0
    negative = 0
    for period in TREND_EMA_PERIODS:
        column = f"EMA_{period}"
        value = _last(data, column)
        if value is None:
            continue
        slope = _slope_pct(data, column, 5)
        relation = _price_relation(price, value)
        averages[str(period)] = {
            "value": value,
            "slope_pct_per_bar": slope,
            "price_relation": relation,
        }
        if relation == "PRICE_ABOVE" and slope is not None and slope > 0:
            positive += 1
        elif relation == "PRICE_BELOW" and slope is not None and slope < 0:
            negative += 1

    count = len(averages)
    if count == 0:
        state = "INSUFFICIENT"
        interpretation = "Orta/uzun vadeli EMA trend değerlendirmesi için veri yok."
    elif positive >= max(2, math.ceil(count * 0.75)):
        state = "POSITIVE"
        interpretation = "Fiyat ve EMA eğimleri orta/uzun vadeli trend tarafında ağırlıklı olarak pozitif uyum gösteriyor."
    elif negative >= max(2, math.ceil(count * 0.75)):
        state = "NEGATIVE"
        interpretation = "Fiyat ve EMA eğimleri orta/uzun vadeli trend tarafında ağırlıklı olarak negatif uyum gösteriyor."
    else:
        state = "MIXED"
        interpretation = "Orta/uzun vadeli ortalamalar aynı yönü teyit etmiyor; trend görünümü geçiş/karışık durumda."
    return {
        "state": state,
        "short_ma": short,
        "ema_trend": averages,
        "interpretation": interpretation,
    }


def _momentum_state(data: pd.DataFrame) -> dict[str, Any]:
    rsi = _last(data, "RSI")
    rsi_cross_50 = _level_cross_state(data, "RSI", 50.0)
    smi = _last(data, "SMI")
    smi_signal = _last(data, "SMI_EMA")
    smi_cross = _cross_state(data, "SMI", "SMI_EMA")
    macd_hist = _last(data, "MACD_HIST")
    macd_hist_prev = _previous(data, "MACD_HIST")
    macd_delta = macd_hist - macd_hist_prev if macd_hist is not None and macd_hist_prev is not None else None

    votes: list[int] = []
    if rsi is not None:
        votes.append(1 if rsi > 55 else -1 if rsi < 45 else 0)
    if smi is not None and smi_signal is not None:
        votes.append(1 if smi > smi_signal else -1 if smi < smi_signal else 0)
    if macd_hist is not None:
        votes.append(1 if macd_hist > 0 else -1 if macd_hist < 0 else 0)
    score = sum(votes)
    if not votes:
        state = "INSUFFICIENT"
        interpretation = "Momentum göstergeleri için yeterli veri yok."
    elif score >= 2:
        state = "POSITIVE"
        interpretation = "RSI, SMI ve MACD ailesi momentum tarafında ağırlıklı olarak pozitif uyum gösteriyor."
    elif score <= -2:
        state = "NEGATIVE"
        interpretation = "RSI, SMI ve MACD ailesi momentum tarafında ağırlıklı olarak negatif uyum gösteriyor."
    else:
        state = "MIXED"
        interpretation = "Momentum göstergeleri aynı yönü teyit etmiyor; sinyaller karışık."

    if macd_hist is not None and macd_delta is not None:
        if macd_hist < 0 < macd_delta:
            histogram_state = "NEGATIVE_BUT_IMPROVING"
        elif macd_hist > 0 and macd_delta > 0:
            histogram_state = "POSITIVE_AND_EXPANDING"
        elif macd_hist > 0 and macd_delta < 0:
            histogram_state = "POSITIVE_BUT_WEAKENING"
        elif macd_hist < 0 and macd_delta < 0:
            histogram_state = "NEGATIVE_AND_WORSENING"
        else:
            histogram_state = "FLAT"
    else:
        histogram_state = "UNAVAILABLE"
    return {
        "state": state,
        "rsi": rsi,
        "rsi_vs_50": rsi_cross_50,
        "smi": smi,
        "smi_signal": smi_signal,
        "smi_cross": smi_cross,
        "macd_hist": macd_hist,
        "macd_hist_delta": macd_delta,
        "macd_hist_state": histogram_state,
        "interpretation": interpretation,
    }


def _participation_state(data: pd.DataFrame) -> dict[str, Any]:
    rvol = _last(data, "RVOL")
    if rvol is None:
        rvol = _last(data, "VOLUME_RATIO")
    cmf = _last(data, "CMF")
    mfi = _last(data, "MFI")
    obv = _last(data, "OBV")
    obv_ma = _last(data, "OBV_SMA")

    if rvol is None:
        state = "INSUFFICIENT"
        interpretation = "Göreceli hacim bulunmadığı için katılım teyidi sınırlı."
    elif rvol >= 1.5:
        state = "STRONG_PARTICIPATION"
        interpretation = f"Göreceli hacim {rvol:.2f}x; hareket normalin belirgin üzerinde katılım görüyor. Yönü fiyat yapısı belirler."
    elif rvol >= 0.8:
        state = "NORMAL_PARTICIPATION"
        interpretation = f"Göreceli hacim {rvol:.2f}x; katılım normal aralıkta, tek başına yön teyidi sayılmaz."
    else:
        state = "LOW_PARTICIPATION"
        interpretation = f"Göreceli hacim {rvol:.2f}x; hareketin hacim katılımı zayıf ve yönlü sinyallerin güvenini azaltıyor."
    return {
        "state": state,
        "rvol": rvol,
        "cmf": cmf,
        "mfi": mfi,
        "obv_relation": (
            "ABOVE_MA" if obv is not None and obv_ma is not None and obv > obv_ma
            else "BELOW_MA" if obv is not None and obv_ma is not None and obv < obv_ma
            else "UNAVAILABLE"
        ),
        "interpretation": interpretation,
    }


def _trend_systems_state(data: pd.DataFrame, price: float | None) -> dict[str, Any]:
    adx = _last(data, "ADX")
    plus_di = _last(data, "PLUS_DI")
    minus_di = _last(data, "MINUS_DI")
    supertrend_dir = _last(data, "SUPERTREND_DIR")
    psar = _last(data, "PSAR")
    tenkan = _last(data, "TENKAN")
    kijun = _last(data, "KIJUN")
    span_a = _last(data, "VISIBLE_SPAN_A")
    span_b = _last(data, "VISIBLE_SPAN_B")

    if span_a is not None and span_b is not None and price is not None:
        cloud_low, cloud_high = sorted((span_a, span_b))
        ichimoku_position = (
            "ABOVE_CLOUD" if price > cloud_high else "BELOW_CLOUD" if price < cloud_low else "INSIDE_CLOUD"
        )
    else:
        ichimoku_position = "UNAVAILABLE"

    if adx is None:
        adx_state = "UNAVAILABLE"
    elif adx >= 25:
        adx_state = "TRENDING"
    elif adx < 20:
        adx_state = "WEAK_TREND"
    else:
        adx_state = "TRANSITION"
    dmi_direction = (
        "BULLISH" if plus_di is not None and minus_di is not None and plus_di > minus_di
        else "BEARISH" if plus_di is not None and minus_di is not None and plus_di < minus_di
        else "UNAVAILABLE"
    )
    interpretation = (
        f"ADX {adx:.1f} ile trend gücü {adx_state.lower()}; DMI yönü {dmi_direction.lower()}."
        if adx is not None
        else "ADX/DMI trend gücü değerlendirmesi kullanılamıyor."
    )
    return {
        "state": adx_state,
        "adx": adx,
        "dmi_direction": dmi_direction,
        "supertrend_direction": supertrend_dir,
        "psar_relation": _price_relation(price, psar),
        "tenkan_kijun": (
            "TENKAN_ABOVE" if tenkan is not None and kijun is not None and tenkan > kijun
            else "TENKAN_BELOW" if tenkan is not None and kijun is not None and tenkan < kijun
            else "UNAVAILABLE"
        ),
        "ichimoku_position": ichimoku_position,
        "interpretation": interpretation,
    }


def _volatility_state(data: pd.DataFrame) -> dict[str, Any]:
    atr_pct = _last(data, "ATR_PCT")
    atr_rank = _last(data, "ATR_RANK")
    bb_width = _last(data, "BB_WIDTH")
    bb_rank = _last(data, "BB_WIDTH_RANK")
    if bb_rank is None:
        state = "UNAVAILABLE"
        interpretation = "Bollinger genişliği tarihsel sırası hesaplanamadı."
    elif bb_rank <= 20:
        state = "SQUEEZE"
        interpretation = "Bollinger bant genişliği tarihsel olarak düşük; volatilite sıkışması var ancak kırılım yönü henüz bu bilgiden çıkarılamaz."
    elif bb_rank >= 80:
        state = "EXPANDED"
        interpretation = "Bollinger bant genişliği tarihsel olarak yüksek; volatilite genişlemiş durumda."
    else:
        state = "NORMAL"
        interpretation = "Volatilite ölçümleri tarihsel olarak orta bölgede."
    return {
        "state": state,
        "atr_pct": atr_pct,
        "atr_rank": atr_rank,
        "bb_width_pct": bb_width,
        "bb_width_rank": bb_rank,
        "interpretation": interpretation,
    }


def build_technical_features(data: pd.DataFrame) -> dict[str, Any]:
    """Create deterministic, presentation-ready technical feature families.

    The function does not produce a trade decision. It turns already calculated
    indicator columns into explicit states and section interpretations so the
    report can explain agreements and conflicts without hiding raw values.
    """
    if data is None or data.empty or "Close" not in data.columns:
        return {
            "available": False,
            "reason": "Teknik feature üretmek için kapanış serisi yok.",
            "sections": {},
        }
    price = _last(data, "Close")
    if price is None:
        return {
            "available": False,
            "reason": "Son kapanış geçerli değil.",
            "sections": {},
        }
    sections = {
        "trend_and_averages": _trend_state(data, price),
        "momentum": _momentum_state(data),
        "participation": _participation_state(data),
        "trend_systems": _trend_systems_state(data, price),
        "volatility": _volatility_state(data),
    }
    return {
        "available": True,
        "price": price,
        "sections": sections,
    }
