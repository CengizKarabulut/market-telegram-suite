from __future__ import annotations

import importlib
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

# GitHub Actions technical_bot altında çalıştığı için repo kökünü sys.path'e
# yalnız preview adaptöründe ekliyoruz. Mevcut production import akışı değişmez.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_market_core = importlib.import_module("market_core")
_report = importlib.import_module("market_core.report")
_serialization = importlib.import_module("market_core.serialization")
build_market_state = _market_core.build_market_state
build_report_contract = _report.build_report_contract
format_telegram_preview = _report.format_telegram_preview
market_state_json = _serialization.market_state_json
report_json = _serialization.report_json


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def canonical_indicators(data: pd.DataFrame) -> dict[str, float]:
    """Mevcut technical_bot hesaplarından V3'ün beklediği küçük canonical seti çıkarır."""
    if data.empty:
        return {}
    row = data.iloc[-1]
    aliases = {
        "RSI": ("RSI",),
        "MACD_HIST": ("MACD_HIST", "MACD Histogram"),
        "SMI": ("SMI",),
        "RVOL": ("RVOL", "Relative Volume"),
        "ADX": ("ADX",),
        "ATR": ("ATR",),
        "BB_WIDTH": ("BB_WIDTH", "BB Width"),
        "EMA20": ("EMA20", "EMA_20", "EMA 20"),
        "EMA50": ("EMA50", "EMA_50", "EMA 50"),
    }
    result: dict[str, float] = {}
    for target, candidates in aliases.items():
        for name in candidates:
            if name not in data.columns:
                continue
            value = _finite(row[name])
            if value is not None:
                result[target] = value
                break
    return result


def data_quality_from_attrs(data: pd.DataFrame) -> dict[str, Any]:
    corporate = data.attrs.get("corporate_action")
    if isinstance(corporate, dict):
        suspected = bool(corporate.get("suspect", False))
    else:
        suspected = bool(corporate)
    return {
        "state": "CRITICAL" if suspected else "OK",
        "critical": suspected,
        "corporate_action": corporate,
        "provider": data.attrs.get("provider"),
        "price_adjustment": data.attrs.get("price_adjustment"),
    }


def build_v3_preview(
    data: pd.DataFrame,
    *,
    symbol: str,
    interval: str,
    benchmark_data: pd.DataFrame | None = None,
    benchmark_name: str = "XU100",
    multi_timeframe_states: dict[str, dict[str, Any]] | None = None,
    scanner_rows: list[Mapping[str, Any]] | None = None,
    ma_level_rows: list[Mapping[str, Any]] | None = None,
) -> tuple[Any, dict[str, Any], str]:
    state = build_market_state(
        data,
        symbol=symbol,
        interval=interval,
        indicators=canonical_indicators(data),
        data_quality=data_quality_from_attrs(data),
        benchmark_data=benchmark_data,
        benchmark_name=benchmark_name,
        multi_timeframe_states=multi_timeframe_states,
        scanner_rows=scanner_rows,
        ma_level_rows=ma_level_rows,
    )
    report = build_report_contract(state)
    return state, report, format_telegram_preview(report)


def write_preview_json(state: Any, report: dict[str, Any], target: Path, stem: str) -> tuple[Path, Path]:
    target.mkdir(parents=True, exist_ok=True)
    state_path = target / f"{stem}_market_state_v3.json"
    report_path = target / f"{stem}_report_v3.json"
    state_path.write_text(market_state_json(state), encoding="utf-8")
    report_path.write_text(report_json(report), encoding="utf-8")
    return state_path, report_path
