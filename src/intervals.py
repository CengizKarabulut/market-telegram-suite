"""Zaman aralığı kayıt defteri.

Her mum aralığı için sağlayıcıdan hangi ham aralığın çekileceğini, ne kadar
geçmiş isteneceğini ve gerekiyorsa hangi kurala göre yeniden örnekleneceğini
tanımlar. 2 saat ve 4 saat hiçbir sağlayıcıda yerel değildir; 1 saatlik
veriden türetilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class IntervalSpec:
    """Bir mum aralığının veri ve görüntüleme tanımı."""

    key: str
    label: str
    source_interval: str
    resample_rule: str | None
    default_period: str
    warmup_period: str
    minutes: float
    intraday: bool


INTERVALS: dict[str, IntervalSpec] = {
    "5m": IntervalSpec("5m", "5 dakika", "5m", None, "1mo", "1mo", 5, True),
    "15m": IntervalSpec("15m", "15 dakika", "15m", None, "3mo", "3mo", 15, True),
    "30m": IntervalSpec("30m", "30 dakika", "30m", None, "6mo", "6mo", 30, True),
    "1h": IntervalSpec("1h", "1 saat", "1h", None, "1y", "1y", 60, True),
    "2h": IntervalSpec("2h", "2 saat", "1h", "2h", "2y", "2y", 120, True),
    "4h": IntervalSpec("4h", "4 saat", "1h", "4h", "2y", "2y", 240, True),
    "1d": IntervalSpec("1d", "1 gün", "1d", None, "2y", "2y", 1440, False),
    "1wk": IntervalSpec("1wk", "1 hafta", "1d", "W-MON", "10y", "10y", 10080, False),
    "1mo": IntervalSpec("1mo", "1 ay", "1d", "MS", "max", "max", 43200, False),
}

RESAMPLE_AGGREGATION = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
}


def resolve(interval: str) -> IntervalSpec:
    """Kullanıcı girdisini bilinen bir aralığa eşler."""
    key = interval.strip().lower()
    aliases = {"60m": "1h", "1wk": "1wk", "1w": "1wk", "w": "1wk", "1month": "1mo", "1M": "1mo", "d": "1d", "1day": "1d"}
    key = aliases.get(key, key)
    if key not in INTERVALS:
        raise ValueError(f"Desteklenmeyen mum aralığı: {interval}. Geçerli değerler: {', '.join(INTERVALS)}")
    return INTERVALS[key]


def resample(data: pd.DataFrame, spec: IntervalSpec) -> pd.DataFrame:
    """Ham barları hedef aralığa toplar; eksik dönemleri düşürür."""
    if not spec.resample_rule:
        return data
    columns = {name: rule for name, rule in RESAMPLE_AGGREGATION.items() if name in data.columns}
    # Gün içi kutuları takvim saatine değil seans başlangıcına hizalanır; aksi halde
    # 10:00–18:00 seansı 4 saatlikte üç eşitsiz bara bölünür.
    origin = "start" if spec.intraday else "start_day"
    resampled = data.resample(spec.resample_rule, label="left", closed="left", origin=origin).agg(columns)
    resampled = resampled.dropna(subset=["Open", "High", "Low", "Close"])
    resampled.attrs.update(data.attrs)
    resampled.attrs["resampled_from"] = spec.source_interval
    return resampled


def usable_ma_periods(bar_count: int, periods: list[int], minimum: int = 6) -> list[int]:
    """Mevcut bar sayısına sığan hareketli ortalama periyotlarını seçer.

    Aylık gibi uzun aralıklarda 377 periyotluk ortalama için yeterli geçmiş
    bulunmaz; rapor hata vermek yerine hesaplanabilen periyotlarla çalışır.
    """
    usable = [period for period in periods if period + 5 <= bar_count]
    return usable if len(usable) >= minimum else periods[:minimum]


def key_ema_periods(available: list[int], preferred: tuple[int, ...] = (21, 55, 233)) -> tuple[int, ...]:
    """Grafik ve trend analizinde öne çıkarılacak üçlüyü mevcut periyotlara göre seçer."""
    if all(period in available for period in preferred):
        return preferred
    if len(available) < 3:
        return tuple(available)
    ordered = sorted(available)
    return (ordered[len(ordered) // 4], ordered[len(ordered) // 2], ordered[-1])


def minimum_bars(spec: IntervalSpec, periods: list[int]) -> int:
    """Bu aralık için kabul edilebilir en düşük bar sayısı."""
    return min(max(periods) + 5, 120) if spec.key in {"1wk", "1mo"} else max(periods) + 5


def bar_word(spec: IntervalSpec) -> str:
    """Sade dil metinlerinde kullanılacak zaman birimi."""
    return {"1d": "işlem günü", "1wk": "hafta", "1mo": "ay"}.get(spec.key, f"{spec.label} mumu")


def describe(spec: IntervalSpec) -> dict[str, Any]:
    return {
        "key": spec.key,
        "label": spec.label,
        "source_interval": spec.source_interval,
        "resampled": bool(spec.resample_rule),
        "intraday": spec.intraday,
        "minutes": spec.minutes,
    }
