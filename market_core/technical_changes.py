from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .models import StructureEvent, TechnicalLevel
from .technical_features import build_technical_features


SHORT_MA_SCORE = {
    "BEARISH_ALIGNMENT": -2,
    "BEARISH_BUT_INCOMPLETE": -1,
    "MIXED": 0,
    "BULLISH_BUT_INCOMPLETE": 1,
    "BULLISH_ALIGNMENT": 2,
}
TREND_SCORE = {"NEGATIVE": -1, "MIXED": 0, "POSITIVE": 1}
ICHIMOKU_SCORE = {"BELOW_CLOUD": -1, "INSIDE_CLOUD": 0, "ABOVE_CLOUD": 1}


SHORT_MA_LABEL = {
    "BEARISH_ALIGNMENT": "negatif hizalanma",
    "BEARISH_BUT_INCOMPLETE": "eksik negatif hizalanma",
    "MIXED": "karışık dizilim",
    "BULLISH_BUT_INCOMPLETE": "eksik pozitif hizalanma",
    "BULLISH_ALIGNMENT": "pozitif hizalanma",
}
TREND_LABEL = {
    "NEGATIVE": "negatif",
    "MIXED": "karışık",
    "POSITIVE": "pozitif",
}
ICHIMOKU_LABEL = {
    "BELOW_CLOUD": "bulut altı",
    "INSIDE_CLOUD": "bulut içi",
    "ABOVE_CLOUD": "bulut üstü",
}


ROLE_CHANGE_LABELS = {
    "FORMER_SUPPORT_RECLAIM": "eski destek geri kazanım seviyesine dönüştü",
    "RECLAIM_FAILED_SUPPORT": "eski desteğin geri kazanımı başarısız oldu",
    "FORMER_SUPPORT_REJECTION": "eski destek aşağıdan reddedildi",
    "RECLAIMED_SUPPORT": "kırılmış destek yeniden kazanıldı",
    "FORMER_RESISTANCE_RETEST": "eski direnç geri test desteğine dönüştü",
    "BREAKOUT_REJECTED_RESISTANCE": "direnç kırılımı reddedildi",
    "BREAKOUT_RECLAIMED_SUPPORT": "kırılan direnç yeniden destek rolü kazandı",
    "FORMER_RESISTANCE_RETEST_HELD": "kırılan direnç geri testte korundu",
}


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _last(data: pd.DataFrame, column: str, offset: int = 0) -> float | None:
    if column not in data.columns or len(data) <= offset:
        return None
    return _number(data[column].iloc[-1 - offset])


def _section(features: dict[str, Any], name: str) -> dict[str, Any]:
    if not features.get("available"):
        return {}
    sections = features.get("sections") or {}
    value = sections.get(name) or {}
    return dict(value) if isinstance(value, dict) else {}


def _add_event(
    events: list[dict[str, Any]],
    *,
    family: str,
    kind: str,
    effect: str,
    importance: int,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not message or any(item.get("message") == message for item in events):
        return
    events.append(
        {
            "family": family,
            "kind": kind,
            "effect": effect,
            "importance": int(importance),
            "message": message,
            "metadata": dict(metadata or {}),
        }
    )


def _transition_effect(previous: str, current: str, score: dict[str, int]) -> str:
    if previous not in score or current not in score:
        return "NEUTRAL"
    if score[current] > score[previous]:
        return "POSITIVE"
    if score[current] < score[previous]:
        return "NEGATIVE"
    return "NEUTRAL"


def _structure_changes(
    events: list[dict[str, Any]],
    structure: dict[str, Any] | None,
    last_index: int,
) -> None:
    if not structure:
        return
    for event in structure.get("events") or []:
        if not isinstance(event, StructureEvent) or event.trigger_index != last_index:
            continue
        if event.kind == "CHOCH_UP":
            message = f"{event.level:.2f} üzerinde CHoCH oluştu; önceki düşüş yapısında ilk yön değişimi uyarısı geldi."
            effect = "POSITIVE"
        elif event.kind == "CHOCH_DOWN":
            message = f"{event.level:.2f} altında CHoCH oluştu; önceki yükseliş yapısında ilk bozulma uyarısı geldi."
            effect = "NEGATIVE"
        elif event.kind == "BOS_UP":
            message = f"{event.level:.2f} üzerinde kapanışla yukarı BOS oluştu."
            effect = "POSITIVE"
        elif event.kind == "BOS_DOWN":
            message = f"{event.level:.2f} altında kapanışla aşağı BOS oluştu."
            effect = "NEGATIVE"
        else:
            continue
        _add_event(
            events,
            family="STRUCTURE",
            kind=event.kind,
            effect=effect,
            importance=4,
            message=message,
            metadata={"level": event.level, "prior_bias": event.prior_bias},
        )

    for level in structure.get("levels") or []:
        if not isinstance(level, TechnicalLevel) or level.last_transition_index != last_index:
            continue
        role_message = ROLE_CHANGE_LABELS.get(level.role)
        if not role_message:
            continue
        effect = "NEUTRAL"
        if level.role in {"RECLAIMED_SUPPORT", "BREAKOUT_RECLAIMED_SUPPORT", "FORMER_RESISTANCE_RETEST_HELD"}:
            effect = "POSITIVE"
        elif level.role in {"RECLAIM_FAILED_SUPPORT", "FORMER_SUPPORT_REJECTION", "BREAKOUT_REJECTED_RESISTANCE"}:
            effect = "NEGATIVE"
        _add_event(
            events,
            family="STRUCTURE",
            kind="LEVEL_ROLE_CHANGE",
            effect=effect,
            importance=3,
            message=f"{level.value:.2f} seviyesi: {role_message}.",
            metadata={"level": level.value, "role": level.role},
        )


def _trend_changes(
    events: list[dict[str, Any]],
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    current_state = str(current.get("state") or "")
    previous_state = str(previous.get("state") or "")
    if current_state != previous_state and current_state in TREND_SCORE and previous_state in TREND_SCORE:
        effect = _transition_effect(previous_state, current_state, TREND_SCORE)
        _add_event(
            events,
            family="TREND",
            kind="EMA_TREND_TRANSITION",
            effect=effect,
            importance=3,
            message=(
                "Orta/uzun EMA trend görünümü "
                f"{TREND_LABEL.get(previous_state, previous_state)} durumdan "
                f"{TREND_LABEL.get(current_state, current_state)} duruma geçti."
            ),
        )

    current_short = current.get("short_ma") or {}
    previous_short = previous.get("short_ma") or {}
    current_short_state = str(current_short.get("state") or "")
    previous_short_state = str(previous_short.get("state") or "")
    if (
        current_short_state != previous_short_state
        and current_short_state in SHORT_MA_SCORE
        and previous_short_state in SHORT_MA_SCORE
    ):
        effect = _transition_effect(previous_short_state, current_short_state, SHORT_MA_SCORE)
        _add_event(
            events,
            family="TREND",
            kind="SHORT_EMA_TRANSITION",
            effect=effect,
            importance=3,
            message=(
                "EMA5/8/13 kısa vadeli yapı "
                f"{SHORT_MA_LABEL.get(previous_short_state, previous_short_state)} durumundan "
                f"{SHORT_MA_LABEL.get(current_short_state, current_short_state)} durumuna geçti."
            ),
        )

    current_emas = current.get("ema_trend") or {}
    previous_emas = previous.get("ema_trend") or {}
    for period in (20, 50, 100, 200):
        key = str(period)
        current_relation = str((current_emas.get(key) or {}).get("price_relation") or "")
        previous_relation = str((previous_emas.get(key) or {}).get("price_relation") or "")
        if current_relation == "PRICE_ABOVE" and previous_relation in {"PRICE_BELOW", "AT_LEVEL"}:
            _add_event(
                events,
                family="TREND",
                kind="PRICE_CROSS_EMA_UP",
                effect="POSITIVE",
                importance=3 if period >= 50 else 2,
                message=f"Fiyat EMA{period} üzerine çıktı.",
                metadata={"period": period},
            )
        elif current_relation == "PRICE_BELOW" and previous_relation in {"PRICE_ABOVE", "AT_LEVEL"}:
            _add_event(
                events,
                family="TREND",
                kind="PRICE_CROSS_EMA_DOWN",
                effect="NEGATIVE",
                importance=3 if period >= 50 else 2,
                message=f"Fiyat EMA{period} altına indi.",
                metadata={"period": period},
            )


def _momentum_changes(
    events: list[dict[str, Any]],
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    rsi_state = str(current.get("rsi_vs_50") or "")
    if rsi_state == "CROSS_UP":
        _add_event(
            events,
            family="MOMENTUM",
            kind="RSI_50_CROSS_UP",
            effect="POSITIVE",
            importance=3,
            message=f"RSI 50 seviyesini yukarı kesti ({_number(current.get('rsi')):.1f}).",
        )
    elif rsi_state == "CROSS_DOWN":
        _add_event(
            events,
            family="MOMENTUM",
            kind="RSI_50_CROSS_DOWN",
            effect="NEGATIVE",
            importance=3,
            message=f"RSI 50 seviyesini aşağı kesti ({_number(current.get('rsi')):.1f}).",
        )
    else:
        current_rsi = _number(current.get("rsi"))
        previous_rsi = _number(previous.get("rsi"))
        if current_rsi is not None and previous_rsi is not None and abs(current_rsi - previous_rsi) >= 3.0:
            rising = current_rsi > previous_rsi
            _add_event(
                events,
                family="MOMENTUM",
                kind="RSI_ACCELERATION",
                effect="POSITIVE" if rising else "NEGATIVE",
                importance=1,
                message=(
                    f"RSI {previous_rsi:.1f} → {current_rsi:.1f}; "
                    + ("momentum toparlanıyor." if rising else "momentum zayıflıyor.")
                ),
            )

    smi_cross = str(current.get("smi_cross") or "")
    if smi_cross == "CROSS_UP":
        _add_event(
            events,
            family="MOMENTUM",
            kind="SMI_CROSS_UP",
            effect="POSITIVE",
            importance=3,
            message="SMI çizgisi yumuşatma çizgisini yukarı kesti.",
        )
    elif smi_cross == "CROSS_DOWN":
        _add_event(
            events,
            family="MOMENTUM",
            kind="SMI_CROSS_DOWN",
            effect="NEGATIVE",
            importance=3,
            message="SMI çizgisi yumuşatma çizgisini aşağı kesti.",
        )

    macd_state = str(current.get("macd_hist_state") or "")
    macd_delta = _number(current.get("macd_hist_delta"))
    if macd_delta is not None and abs(macd_delta) > 1e-12:
        if macd_state == "NEGATIVE_BUT_IMPROVING":
            effect = "POSITIVE"
            message = "MACD histogramı hâlâ negatif bölgede ancak önceki bara göre toparlanıyor."
        elif macd_state == "POSITIVE_AND_EXPANDING":
            effect = "POSITIVE"
            message = "MACD histogramı pozitif bölgede ve önceki bara göre genişliyor."
        elif macd_state == "POSITIVE_BUT_WEAKENING":
            effect = "NEGATIVE"
            message = "MACD histogramı pozitif bölgede kalmasına rağmen önceki bara göre zayıflıyor."
        elif macd_state == "NEGATIVE_AND_WORSENING":
            effect = "NEGATIVE"
            message = "MACD histogramı negatif bölgede ve önceki bara göre daha da zayıflıyor."
        else:
            effect = "NEUTRAL"
            message = "MACD histogramında önceki bara göre sınırlı değişim var."
        _add_event(
            events,
            family="MOMENTUM",
            kind="MACD_HIST_CHANGE",
            effect=effect,
            importance=2,
            message=message,
            metadata={"delta": macd_delta, "state": macd_state},
        )


def _participation_changes(
    events: list[dict[str, Any]],
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    current_state = str(current.get("state") or "")
    previous_state = str(previous.get("state") or "")
    current_rvol = _number(current.get("rvol"))
    previous_rvol = _number(previous.get("rvol"))
    if current_state != previous_state and current_state and previous_state:
        _add_event(
            events,
            family="PARTICIPATION",
            kind="RVOL_REGIME_CHANGE",
            effect="NEUTRAL",
            importance=2,
            message=(
                "Hacim katılım rejimi değişti"
                + (
                    f" ({previous_rvol:.2f}x → {current_rvol:.2f}x)."
                    if current_rvol is not None and previous_rvol is not None
                    else "."
                )
            ),
            metadata={"previous_state": previous_state, "current_state": current_state},
        )
    elif current_rvol is not None and previous_rvol is not None and abs(current_rvol - previous_rvol) >= 0.30:
        _add_event(
            events,
            family="PARTICIPATION",
            kind="RVOL_CHANGE",
            effect="NEUTRAL",
            importance=1,
            message=f"Göreceli hacim {previous_rvol:.2f}x → {current_rvol:.2f}x değişti.",
        )


def _trend_system_changes(
    events: list[dict[str, Any]],
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    current_dmi = str(current.get("dmi_direction") or "")
    previous_dmi = str(previous.get("dmi_direction") or "")
    if current_dmi != previous_dmi and current_dmi in {"BULLISH", "BEARISH"}:
        _add_event(
            events,
            family="TREND_SYSTEM",
            kind="DMI_DIRECTION_CHANGE",
            effect="POSITIVE" if current_dmi == "BULLISH" else "NEGATIVE",
            importance=3,
            message=(
                "DMI yönü yukarı tarafa döndü (+DI > -DI)."
                if current_dmi == "BULLISH"
                else "DMI yönü aşağı tarafa döndü (-DI > +DI)."
            ),
        )

    current_adx = _number(current.get("adx"))
    previous_adx = _number(previous.get("adx"))
    if current_adx is not None and previous_adx is not None and abs(current_adx - previous_adx) >= 2.0:
        rising = current_adx > previous_adx
        effect = "NEUTRAL"
        if rising and current_dmi == "BULLISH":
            effect = "POSITIVE"
        elif rising and current_dmi == "BEARISH":
            effect = "NEGATIVE"
        direction_text = "yükseliş" if current_dmi == "BULLISH" else "düşüş" if current_dmi == "BEARISH" else "mevcut"
        _add_event(
            events,
            family="TREND_SYSTEM",
            kind="ADX_CHANGE",
            effect=effect,
            importance=2,
            message=(
                f"ADX {previous_adx:.1f} → {current_adx:.1f}; {direction_text} yönündeki trend gücü "
                + ("artıyor." if rising else "zayıflıyor.")
            ),
        )

    current_psar = str(current.get("psar_relation") or "")
    previous_psar = str(previous.get("psar_relation") or "")
    if current_psar == "PRICE_ABOVE" and previous_psar in {"PRICE_BELOW", "AT_LEVEL"}:
        _add_event(
            events,
            family="TREND_SYSTEM",
            kind="PSAR_FLIP_UP",
            effect="POSITIVE",
            importance=2,
            message="Fiyat Parabolic SAR seviyesinin üzerine geçti.",
        )
    elif current_psar == "PRICE_BELOW" and previous_psar in {"PRICE_ABOVE", "AT_LEVEL"}:
        _add_event(
            events,
            family="TREND_SYSTEM",
            kind="PSAR_FLIP_DOWN",
            effect="NEGATIVE",
            importance=2,
            message="Fiyat Parabolic SAR seviyesinin altına geçti.",
        )

    current_cloud = str(current.get("ichimoku_position") or "")
    previous_cloud = str(previous.get("ichimoku_position") or "")
    if current_cloud != previous_cloud and current_cloud in ICHIMOKU_SCORE and previous_cloud in ICHIMOKU_SCORE:
        effect = _transition_effect(previous_cloud, current_cloud, ICHIMOKU_SCORE)
        _add_event(
            events,
            family="TREND_SYSTEM",
            kind="ICHIMOKU_POSITION_CHANGE",
            effect=effect,
            importance=3,
            message=(
                "Ichimoku fiyat konumu "
                f"{ICHIMOKU_LABEL.get(previous_cloud, previous_cloud)} → "
                f"{ICHIMOKU_LABEL.get(current_cloud, current_cloud)} değişti."
            ),
        )


def _volatility_changes(
    events: list[dict[str, Any]],
    current: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    current_state = str(current.get("state") or "")
    previous_state = str(previous.get("state") or "")
    if current_state != previous_state and current_state not in {"", "UNAVAILABLE"} and previous_state not in {"", "UNAVAILABLE"}:
        labels = {"SQUEEZE": "sıkışma", "NORMAL": "normal", "EXPANDED": "genişleme"}
        _add_event(
            events,
            family="VOLATILITY",
            kind="VOLATILITY_REGIME_CHANGE",
            effect="NEUTRAL",
            importance=2,
            message=(
                "Volatilite rejimi "
                f"{labels.get(previous_state, previous_state.lower())} → "
                f"{labels.get(current_state, current_state.lower())} değişti."
            ),
        )


def build_technical_changes(
    data: pd.DataFrame,
    current_features: dict[str, Any] | None = None,
    structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Son kapanışta neyin değiştiğini geçmişe bakmadan deterministik olarak açıklar.

    Önceki durum yalnız ``data.iloc[:-1]`` ile yeniden hesaplanır; son barın
    değerleri önceki snapshot'a sızamaz. Çıktı genel AL/SAT kararı değildir;
    yeni kesişimleri, rejim geçişlerini, güçlenme/zayıflamayı ve yapısal olayları
    ayrı bir değişim katmanı olarak raporlar.
    """
    if data is None or len(data) < 2 or "Close" not in data.columns:
        return {
            "available": False,
            "state": "INSUFFICIENT",
            "headline": "Değişim analizi için en az iki bar gerekir.",
            "events": [],
            "directional_counts": {"positive": 0, "negative": 0, "neutral": 0},
        }

    current = dict(current_features or build_technical_features(data))
    previous = build_technical_features(data.iloc[:-1].copy())
    if not current.get("available") or not previous.get("available"):
        return {
            "available": False,
            "state": "INSUFFICIENT",
            "headline": "Teknik feature snapshot'ları değişim analizi için yeterli değil.",
            "events": [],
            "directional_counts": {"positive": 0, "negative": 0, "neutral": 0},
        }

    events: list[dict[str, Any]] = []
    _structure_changes(events, structure, len(data) - 1)
    _trend_changes(
        events,
        _section(current, "trend_and_averages"),
        _section(previous, "trend_and_averages"),
    )
    _momentum_changes(
        events,
        _section(current, "momentum"),
        _section(previous, "momentum"),
    )
    _participation_changes(
        events,
        _section(current, "participation"),
        _section(previous, "participation"),
    )
    _trend_system_changes(
        events,
        _section(current, "trend_systems"),
        _section(previous, "trend_systems"),
    )
    _volatility_changes(
        events,
        _section(current, "volatility"),
        _section(previous, "volatility"),
    )

    family_order = {
        "STRUCTURE": 0,
        "TREND": 1,
        "MOMENTUM": 2,
        "TREND_SYSTEM": 3,
        "PARTICIPATION": 4,
        "VOLATILITY": 5,
    }
    events.sort(
        key=lambda item: (
            -int(item.get("importance", 0)),
            family_order.get(str(item.get("family")), 99),
            str(item.get("kind")),
        )
    )

    positive = sum(1 for item in events if item.get("effect") == "POSITIVE")
    negative = sum(1 for item in events if item.get("effect") == "NEGATIVE")
    neutral = sum(1 for item in events if item.get("effect") == "NEUTRAL")
    if positive and negative:
        state = "MIXED_CHANGE"
        headline = "Son barda iyileşen ve bozulan teknik göstergeler birlikte var; değişim yönü karışık."
    elif positive:
        state = "IMPROVING"
        headline = "Son bardaki teknik değişimlerin ağırlığı iyileşme yönünde; bu tek başına trend dönüşü teyidi değildir."
    elif negative:
        state = "DETERIORATING"
        headline = "Son bardaki teknik değişimlerin ağırlığı bozulma yönünde; mevcut yapı ve seviyelerle birlikte okunmalı."
    elif events:
        state = "ROTATION"
        headline = "Son barda yönsüz fakat önemli katılım/volatilite veya rejim değişimleri var."
    else:
        state = "STABLE"
        headline = "Son barda yeni kesişim veya belirgin teknik durum değişimi tespit edilmedi."

    return {
        "available": True,
        "state": state,
        "headline": headline,
        "events": events[:12],
        "directional_counts": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
        },
        "previous_timestamp": data.index[-2],
        "current_timestamp": data.index[-1],
        "no_lookahead": True,
    }
