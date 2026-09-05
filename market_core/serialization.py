from __future__ import annotations

import json
import math
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - core CI installs numpy
    np = None

try:
    import pandas as pd
except ImportError:  # pragma: no cover - core CI installs pandas
    pd = None


STATE_SCHEMA = "market-state/v3"
REPORT_SCHEMA = "market-report/v3"
ENGINE_VERSION = "3.0.0-preview"


def _finite_number(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def to_primitive(value: Any) -> Any:
    """Canonical state içindeki Python/pandas/numpy nesnelerini JSON-safe hale getirir.

    Dönüşüm presentation katmanında gizli hesap yapmaz; yalnız veri biçimini
    normalize eder. NaN/inf JSON'a sızmaz, `None` olur.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _finite_number(value)
    if isinstance(value, Enum):
        return to_primitive(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if pd is not None and isinstance(value, pd.Timestamp):
        return value.isoformat()
    if np is not None:
        if isinstance(value, np.generic):
            return to_primitive(value.item())
        if isinstance(value, np.ndarray):
            return [to_primitive(item) for item in value.tolist()]
    if is_dataclass(value):
        return {field.name: to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_primitive(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    return str(value)


def market_state_dict(state: Any) -> dict[str, Any]:
    payload = to_primitive(state)
    if not isinstance(payload, dict):
        raise TypeError("MarketState sözleşmesi sözlük biçimine dönüştürülemedi.")
    return {
        "schema": STATE_SCHEMA,
        "engine_version": ENGINE_VERSION,
        **payload,
    }


def market_state_json(state: Any, *, indent: int | None = 2) -> str:
    return json.dumps(
        market_state_dict(state),
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
        allow_nan=False,
    )


def report_json(report: dict[str, Any], *, indent: int | None = 2) -> str:
    payload = to_primitive(report)
    if not isinstance(payload, dict):
        raise TypeError("Report contract sözlük biçimine dönüştürülemedi.")
    payload.setdefault("schema", REPORT_SCHEMA)
    payload.setdefault("engine_version", ENGINE_VERSION)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=indent, allow_nan=False)
