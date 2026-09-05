from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


TARAMABOT_STRATEGY_LABELS: dict[str, tuple[str, str]] = {
    "macd_cross": ("M-1", "MACD Pozitif Kesişim"),
    "h8": ("S-M-1", "SMI/MACD Momentum"),
    "i9": ("S-M-V-1", "SMI/MACD Güçlü Onay"),
    "ema": ("E-V-1", "EMA Trend + Hacim"),
    "rsi_macd": ("R-M-V-1", "RSI + MACD + Hacim"),
    "new_scan": ("A-M-V-1", "SMA + MACD + Hacim"),
    "rsi": ("R-V-1", "RSI Momentum"),
    # Legacy smi_macd has two variants. We intentionally keep the raw strategy
    # name because state metadata is not always sufficient to disambiguate them.
    "smi_macd": ("SMI-MACD-LEGACY", "Legacy SMI/MACD"),
}


def _symbol(value: Any) -> str:
    return str(value or "").strip().upper().removesuffix(".IS").removesuffix(".E")


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_taramabot_state_rows(
    path: str | Path,
    *,
    symbol: str | None = None,
    max_rows: int = 25,
) -> list[dict[str, Any]]:
    """Read taramabot's persisted signal history without claiming it is live.

    `signal_history` records what the scanner emitted in the past. They are
    therefore normalized as HISTORICAL evidence. A separate current-snapshot
    adapter will be used for the question "does the setup still match now?".
    """
    payload = _load_json(path)
    history = payload.get("signal_history", []) if isinstance(payload, Mapping) else []
    if not isinstance(history, list):
        return []

    wanted = _symbol(symbol) if symbol else ""
    rows: list[dict[str, Any]] = []
    for event in reversed(history):
        if not isinstance(event, Mapping):
            continue
        event_symbol = _symbol(event.get("symbol"))
        if wanted and event_symbol != wanted:
            continue
        strategy = str(event.get("strategy") or "").strip()
        code, name = TARAMABOT_STRATEGY_LABELS.get(
            strategy,
            (strategy.upper() or "UNKNOWN", strategy or "Bilinmeyen tarama"),
        )
        metadata = {
            key: value
            for key, value in event.items()
            if key
            not in {
                "symbol",
                "period",
                "strategy",
                "bar_time",
                "detected_at",
                "price",
            }
        }
        rows.append(
            {
                "source": "taramabot",
                "scanner_code": code,
                "scanner_name": name,
                "symbol": event_symbol,
                "timeframe": event.get("period"),
                "signal": "AL",
                "state": "HISTORICAL",
                "triggered_at": event.get("detected_at") or event.get("bar_time"),
                "trigger_price": event.get("price"),
                "data_quality": {
                    "kind": "persisted_signal_history",
                    "current_match_unknown": True,
                    "raw_strategy": strategy,
                    "metadata": metadata,
                },
            }
        )
        if max_rows > 0 and len(rows) >= max_rows:
            break
    return rows


def load_scanner_snapshot_rows(
    path: str | Path,
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    """Read a future/current versioned scanner snapshot or a plain row list."""
    payload = _load_json(path)
    if isinstance(payload, Mapping):
        rows = payload.get("signals", payload.get("rows", []))
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    wanted = _symbol(symbol) if symbol else ""
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if wanted and _symbol(row.get("symbol") or row.get("ticker")) != wanted:
            continue
        result.append(dict(row))
    return result


def load_ma_watchlist_rows(
    path: str | Path,
    *,
    symbol: str | None = None,
    timeframes: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Read ma-reaction-scanner `ma_watchlist.csv` with no formula duplication."""
    wanted_symbol = _symbol(symbol) if symbol else ""
    wanted_timeframes = {str(item).strip().lower() for item in (timeframes or []) if str(item).strip()}
    result: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            row_symbol = _symbol(row.get("symbol") or row.get("Varlik") or row.get("Varlık"))
            if wanted_symbol and row_symbol != wanted_symbol:
                continue
            timeframe = str(row.get("timeframe") or row.get("Zaman Dilimi") or "").strip().lower()
            if wanted_timeframes and timeframe not in wanted_timeframes:
                continue
            result.append(dict(row))
    return result
