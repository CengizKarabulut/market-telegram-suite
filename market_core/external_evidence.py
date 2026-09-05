from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .models import TechnicalLevel


_TIMEFRAME_ALIASES = {
    "5M": "5m",
    "15M": "15m",
    "30M": "30m",
    "45M": "45m",
    "1H": "1h",
    "2H": "2h",
    "4H": "4h",
    "1D": "1d",
    "D": "1d",
    "1W": "1wk",
    "1WK": "1wk",
    "W": "1wk",
    "1M": "1mo",
    "1MO": "1mo",
}


def normalize_timeframe(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return _TIMEFRAME_ALIASES.get(raw.upper(), raw.lower())


def _float_or_none(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int_or_none(value: Any) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return default


def _list_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_scan_side(value: Any) -> str:
    raw = str(value or "").strip().casefold()
    if raw in {"al", "buy", "long", "bull", "bullish", "yukari", "yukarı"}:
        return "BUY"
    if raw in {"sat", "sell", "short", "bear", "bearish", "asagi", "aşağı"}:
        return "SELL"
    return "NEUTRAL"


def _normalize_scan_state(value: Any) -> str:
    raw = str(value or "ACTIVE").strip().casefold()
    aliases = {
        "new": "NEW",
        "yeni": "NEW",
        "aday": "NEW",
        "active": "ACTIVE",
        "aktif": "ACTIVE",
        "confirmed": "CONFIRMED",
        "teyitli": "CONFIRMED",
        "teyit": "CONFIRMED",
        "weakening": "WEAKENING",
        "zayifliyor": "WEAKENING",
        "zayıflıyor": "WEAKENING",
        "invalidated": "INVALIDATED",
        "gecersiz": "INVALIDATED",
        "geçersiz": "INVALIDATED",
        "expired": "EXPIRED",
        "suresi doldu": "EXPIRED",
        "süresi doldu": "EXPIRED",
    }
    return aliases.get(raw, str(value or "ACTIVE").strip().upper())


def _normalize_ma_side(value: Any) -> str:
    if isinstance(value, (int, float)):
        if float(value) > 0:
            return "SUPPORT"
        if float(value) < 0:
            return "RESISTANCE"
    raw = str(value or "").strip().casefold()
    if raw in {"destek", "support", "sup", "+1", "1"}:
        return "SUPPORT"
    if raw in {"direnc", "direnç", "diren?", "resistance", "res", "-1"}:
        return "RESISTANCE"
    return "NEUTRAL"


@dataclass(frozen=True)
class ScanSignal:
    source: str = "taramabot"
    source_version: str = ""
    scanner_code: str = ""
    scanner_name: str = ""
    symbol: str = ""
    timeframe: str = ""
    side: str = "NEUTRAL"
    state: str = "ACTIVE"
    triggered_at: Any = None
    age_bars: int | None = None
    trigger_price: float | None = None
    conditions_met: list[str] = field(default_factory=list)
    conditions_failed: list[str] = field(default_factory=list)
    invalidation_level: float | None = None
    exit_condition: str = ""
    strength: float | None = None
    confidence: float | None = None
    data_quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MALevelEvidence:
    source: str = "ma-reaction-scanner"
    source_version: str = ""
    symbol: str = ""
    timeframe: str = ""
    side: str = "NEUTRAL"
    zone_low: float | None = None
    zone_high: float | None = None
    zone_mid: float | None = None
    distance_pct: float | None = None
    distance_atr: float | None = None
    ma_list: list[str] = field(default_factory=list)
    best_ma: str = ""
    best_ma_type: str = ""
    best_ma_period: int | None = None
    best_ma_value: float | None = None
    level_touches: int | None = None
    hold_rate_pct: float | None = None
    median_bounce_atr: float | None = None
    reaction_1atr_rate_pct: float | None = None
    reaction_2atr_rate_pct: float | None = None
    median_penetration_atr: float | None = None
    cross_per_100: float | None = None
    plateau_ratio: float | None = None
    zone_score: float | None = None
    zone_quality: str = ""
    zone_member_count: int | None = None
    analysis_basis: str = "nominal"
    data_quality: dict[str, Any] = field(default_factory=dict)


def scan_signal_from_mapping(row: Mapping[str, Any]) -> ScanSignal:
    """Taramabot benzeri bir kaydi versioned ScanSignal contract'ina normalize eder."""
    return ScanSignal(
        source=str(_first(row, "source", default="taramabot")),
        source_version=str(_first(row, "source_version", "version", "scanner_version", default="")),
        scanner_code=str(_first(row, "scanner_code", "signal_code", "code", "strategy_code", default="")),
        scanner_name=str(_first(row, "scanner_name", "signal_name", "name", "strategy_name", default="")),
        symbol=str(_first(row, "symbol", "ticker", "code_symbol", default="")).upper(),
        timeframe=normalize_timeframe(_first(row, "timeframe", "interval", "tf", default="")),
        side=_normalize_scan_side(_first(row, "side", "signal", "signal_side", "direction", default="")),
        state=_normalize_scan_state(_first(row, "state", "signal_state", "status", default="ACTIVE")),
        triggered_at=_first(row, "triggered_at", "signal_time", "timestamp", "time"),
        age_bars=_int_or_none(_first(row, "age_bars", "bars_since", "signal_age")),
        trigger_price=_float_or_none(_first(row, "trigger_price", "price", "signal_price")),
        conditions_met=_list_value(_first(row, "conditions_met", "matched_conditions", "conditions", default=[])),
        conditions_failed=_list_value(_first(row, "conditions_failed", "missing_conditions", default=[])),
        invalidation_level=_float_or_none(_first(row, "invalidation_level", "stop", "stop_level")),
        exit_condition=str(_first(row, "exit_condition", "exit_rule", default="")),
        strength=_float_or_none(_first(row, "strength", "score")),
        confidence=_float_or_none(_first(row, "confidence", "signal_confidence")),
        data_quality=dict(_first(row, "data_quality", default={}) or {}),
    )


def ma_level_from_mapping(row: Mapping[str, Any]) -> MALevelEvidence:
    """ma-reaction-scanner watchlist satirini canonical MA level contract'ina cevirir."""
    zone_low = _float_or_none(_first(row, "zone_low", "Bolge Alt", "Bölge Alt"))
    zone_high = _float_or_none(_first(row, "zone_high", "Bolge Ust", "Bölge Üst"))
    zone_mid = _float_or_none(_first(row, "zone_mid", "Bolge Orta", "Bölge Orta"))
    if zone_mid is None and zone_low is not None and zone_high is not None:
        zone_mid = (zone_low + zone_high) / 2.0
    if zone_mid is None:
        zone_mid = _float_or_none(_first(row, "best_ma_value", "current_ma", "En Iyi MA Degeri"))

    return MALevelEvidence(
        source=str(_first(row, "source", default="ma-reaction-scanner")),
        source_version=str(_first(row, "source_version", "version", default="")),
        symbol=str(_first(row, "symbol", "Varlik", "Varlık", "ticker", default="")).upper(),
        timeframe=normalize_timeframe(_first(row, "timeframe", "Zaman Dilimi", "interval", default="")),
        side=_normalize_ma_side(_first(row, "side", "Taraf", default="")),
        zone_low=zone_low,
        zone_high=zone_high,
        zone_mid=zone_mid,
        distance_pct=_float_or_none(_first(row, "distance_pct", "Uzaklik %", "Uzaklık %")),
        distance_atr=_float_or_none(_first(row, "distance_atr", "Uzak ATR")),
        ma_list=_list_value(_first(row, "ma_list", "Ortalamalar", "ma", default=[])),
        best_ma=str(_first(row, "best_ma", "En Iyi MA", default="")),
        best_ma_type=str(_first(row, "best_ma_type", "En Iyi MA Tipi", default="")),
        best_ma_period=_int_or_none(_first(row, "best_ma_period", "En Iyi Periyot")),
        best_ma_value=_float_or_none(_first(row, "best_ma_value", "En Iyi MA Degeri")),
        level_touches=_int_or_none(_first(row, "level_touches", "Temas")),
        hold_rate_pct=_float_or_none(_first(row, "hold_rate_pct", "Tutma %")),
        median_bounce_atr=_float_or_none(_first(row, "median_bounce_atr", "Sicrama ATR", "Sıçrama ATR")),
        reaction_1atr_rate_pct=_float_or_none(_first(row, "reaction_1atr_rate_pct")),
        reaction_2atr_rate_pct=_float_or_none(_first(row, "reaction_2atr_rate_pct")),
        median_penetration_atr=_float_or_none(_first(row, "median_penetration_atr")),
        cross_per_100=_float_or_none(_first(row, "cross_per_100")),
        plateau_ratio=_float_or_none(_first(row, "plateau_ratio", "Plato")),
        zone_score=_float_or_none(_first(row, "zone_score", "Bolge Skoru", "Bölge Skoru", "median_level_score")),
        zone_quality=str(_first(row, "zone_quality", "Bolge Kalitesi", "Bölge Kalitesi", "confidence", default="")),
        zone_member_count=_int_or_none(_first(row, "zone_member_count", "Bolge Uye Sayisi", "Bölge Üye Sayısı")),
        analysis_basis=str(_first(row, "analysis_basis", "Analiz Bazi", "Analiz Bazı", default="nominal")),
        data_quality=dict(_first(row, "data_quality", default={}) or {}),
    )


def _level_quality_confidence(item: MALevelEvidence) -> float:
    """Gozlemsel seviye kalitesini 0-1 internal evidence guvenine normalize eder.

    Bu deger gelecek basari olasiligi degildir; yalnizca level ranking icin
    gozlemsel kanit kalitesidir.
    """
    if item.zone_score is not None:
        return min(max(float(item.zone_score) / 100.0, 0.0), 1.0)
    quality = item.zone_quality.casefold()
    if "gucl" in quality or "güçl" in quality:
        return 0.55
    if "orta" in quality:
        return 0.40
    if "zay" in quality:
        return 0.25
    return 0.20


def ma_level_to_technical_level(item: MALevelEvidence, price: float) -> TechnicalLevel | None:
    if item.zone_mid is None or not math.isfinite(float(item.zone_mid)):
        return None
    value = float(item.zone_mid)
    role = item.side if item.side in {"SUPPORT", "RESISTANCE"} else (
        "SUPPORT" if value < price else "RESISTANCE" if value > price else "NEUTRAL"
    )
    return TechnicalLevel(
        value=value,
        zone_low=item.zone_low,
        zone_high=item.zone_high,
        source="MA_OBSERVED_LEVEL",
        role=role,
        distance_pct=(value / price - 1.0) * 100 if price else item.distance_pct,
        distance_atr=item.distance_atr,
        tests=item.level_touches or 0,
        confidence=_level_quality_confidence(item),
        metadata={
            "source_repo": item.source,
            "source_version": item.source_version,
            "timeframe": item.timeframe,
            "ma_list": item.ma_list,
            "best_ma": item.best_ma,
            "best_ma_type": item.best_ma_type,
            "best_ma_period": item.best_ma_period,
            "best_ma_value": item.best_ma_value,
            "hold_rate_pct": item.hold_rate_pct,
            "median_bounce_atr": item.median_bounce_atr,
            "reaction_1atr_rate_pct": item.reaction_1atr_rate_pct,
            "reaction_2atr_rate_pct": item.reaction_2atr_rate_pct,
            "median_penetration_atr": item.median_penetration_atr,
            "cross_per_100": item.cross_per_100,
            "plateau_ratio": item.plateau_ratio,
            "zone_score": item.zone_score,
            "zone_quality": item.zone_quality,
            "zone_member_count": item.zone_member_count,
            "analysis_basis": item.analysis_basis,
            "confidence_semantics": "observational_level_quality_not_probability",
        },
    )


def ma_levels_for_interval(
    items: Iterable[MALevelEvidence],
    *,
    price: float,
    interval: str,
) -> list[TechnicalLevel]:
    """Yalniz raporun kendi timeframe'indeki MA bolgelerini live Level Engine'e alir."""
    wanted = normalize_timeframe(interval)
    result: list[TechnicalLevel] = []
    for item in items:
        if normalize_timeframe(item.timeframe) != wanted:
            continue
        level = ma_level_to_technical_level(item, price)
        if level is not None:
            result.append(level)
    return result
