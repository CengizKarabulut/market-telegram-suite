"""Zaman aralığı kayıt defteri.

Teknik analiz ve tarama katmanı yalnızca dört zaman dilimini destekler:
1 saat, 4 saat, 1 gün ve 1 hafta. 4 saatlik mum 1 saatlik veriden, haftalık
mum ise günlük veriden türetilir.
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
    "1h": IntervalSpec("1h", "1 saat", "1h", None, "1y", "1y", 60, True),
    "4h": IntervalSpec("4h", "4 saat", "1h", "4h", "2y", "2y", 240, True),
    "1d": IntervalSpec("1d", "1 gün", "1d", None, "2y", "2y", 1440, False),
    "1wk": IntervalSpec("1wk", "1 hafta", "1d", "W-MON", "10y", "10y", 10080, False),
}

RESAMPLE_AGGREGATION = {
    "Open": "first",
    "High": "max",
    "Low": "min",
    "Close": "last",
    "Volume": "sum",
}


def resolve(interval: str) -> IntervalSpec:
    """Kullanıcı girdisini bilinen dört aralıktan birine eşler."""
    key = interval.strip().lower()
    aliases = {
        "60m": "1h",
        "1w": "1wk",
        "w": "1wk",
        "d": "1d",
        "1day": "1d",
    }
    key = aliases.get(key, key)
    if key not in INTERVALS:
        raise ValueError(
            f"Desteklenmeyen mum aralığı: {interval}. "
            f"Geçerli değerler: {', '.join(INTERVALS)}"
        )
    return INTERVALS[key]


def _session_chunks(data: pd.DataFrame, bars_per_group: int, columns: dict[str, str]) -> pd.DataFrame:
    """Gün içi barları seans içindeki konumlarına göre gruplar.

    Takvim saatine hizalama, seans sonundaki kapanış barını ayrı bir kutuya
    düşürüp tek barlık sahte mum üretir. Borsalar (ve TradingView) barları
    seans başından itibaren sayar; burada da aynı yöntem kullanılır.
    Gün sonunda artan barlar, sahte kısa mum oluşmasın diye son gruba eklenir.
    """
    frames = []
    for _, day in data.groupby(pd.DatetimeIndex(data.index).date, sort=True):
        count = len(day)
        if not count:
            continue
        full_groups = count // bars_per_group
        remainder = count % bars_per_group
        last_group = max(full_groups - 1, 0)
        groups = [
            last_group if (remainder and full_groups and index >= full_groups * bars_per_group)
            else min(index // bars_per_group, last_group)
            for index in range(count)
        ]
        aggregated = day.groupby(groups).agg(columns)
        aggregated.index = [day.index[group * bars_per_group] for group in aggregated.index]
        frames.append(aggregated)
    if not frames:
        return data.iloc[:0]
    result = pd.concat(frames)
    result.index = pd.DatetimeIndex(result.index)
    return result.sort_index()


def resample(data: pd.DataFrame, spec: IntervalSpec) -> pd.DataFrame:
    """Ham barları hedef aralığa toplar; eksik dönemleri düşürür."""
    if not spec.resample_rule:
        return data
    columns = {
        name: rule
        for name, rule in RESAMPLE_AGGREGATION.items()
        if name in data.columns
    }
    if spec.intraday:
        source = INTERVALS.get(spec.source_interval)
        bars_per_group = max(int(spec.minutes // source.minutes), 1) if source else 1
        resampled = _session_chunks(data, bars_per_group, columns)
    else:
        resampled = data.resample(
            spec.resample_rule,
            label="left",
            closed="left",
            origin="start_day",
        ).agg(columns)
    resampled = resampled.dropna(subset=["Open", "High", "Low", "Close"])
    resampled.attrs.update(data.attrs)
    resampled.attrs["resampled_from"] = spec.source_interval
    resampled.attrs["bars_per_group"] = spec.minutes
    return resampled


def usable_ma_periods(bar_count: int, periods: list[int], minimum: int = 6) -> list[int]:
    """Mevcut bar sayısına sığan hareketli ortalama periyotlarını seçer."""
    usable = [period for period in periods if period + 5 <= bar_count]
    return usable if len(usable) >= minimum else periods[:minimum]


def key_ema_periods(
    available: list[int], preferred: tuple[int, ...] = (21, 55, 233)
) -> tuple[int, ...]:
    """Öne çıkarılan Fibonacci üçlüsünden hesaplanabilenleri döndürür."""
    return tuple(period for period in preferred if period in available)


def missing_ma_periods(bar_count: int, periods: list[int]) -> list[int]:
    """Veri yetersizliği nedeniyle hesaplanamayan periyotları listeler."""
    return [period for period in periods if period + 5 > bar_count]


# Hacim profili (100 bar), uyumsuzluk taraması (60 bar) ve yapı pivotları için
# gereken mutlak alt sınır. Yeni halka arzlarda uzun ortalamalar hesaplanamaz
# ama rapor yine de üretilebilir.
ABSOLUTE_MINIMUM_BARS = 120


def minimum_bars(spec: IntervalSpec, periods: list[int]) -> int:
    """Bu aralık için kabul edilebilir en düşük bar sayısı."""
    return min(max(periods) + 5, ABSOLUTE_MINIMUM_BARS)


def bar_word(spec: IntervalSpec) -> str:
    """Sade dil metinlerinde kullanılacak zaman birimi."""
    return {
        "1d": "işlem günü",
        "1wk": "hafta",
    }.get(spec.key, f"{spec.label} mumu")


def describe(spec: IntervalSpec) -> dict[str, Any]:
    return {
        "key": spec.key,
        "label": spec.label,
        "source_interval": spec.source_interval,
        "resampled": bool(spec.resample_rule),
        "intraday": spec.intraday,
        "minutes": spec.minutes,
    }


# Yüzdelik hesaplarında her aralıkta anlamlı bir takvim penceresi korunur.
RANK_WINDOWS = {
    "1h": 500,    # ~9 ay
    "4h": 250,    # ~1 yıl
    "1d": 252,    # 1 yıl
    "1wk": 104,   # 2 yıl
}


def rank_window(interval: str) -> int:
    """Yüzdelik sıralamalarının bu aralıktaki geriye bakış penceresi."""
    return RANK_WINDOWS.get(resolve(interval).key, 252)
