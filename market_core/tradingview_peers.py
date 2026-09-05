from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from .company_classification import CompanyClassification, classify_company
from .peer_benchmarks import PeerObservation


TRADINGVIEW_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "sector",
    "industry",
    "market_cap_basic",
    "fiscal_period_current",
    "fiscal_period_end_current",
    "total_revenue_yoy_growth_ttm",
    "net_income_yoy_growth_ttm",
    "gross_margin",
    "ebitda_margin_ttm",
    "after_tax_margin",
    "return_on_equity",
    "return_on_assets",
    "return_on_invested_capital",
    "current_ratio",
    "price_earnings_ttm",
    "price_book_fq",
    "price_revenue_ttm",
    "enterprise_value_ebitda_current",
)


_PERCENT_FIELDS: Mapping[str, str] = {
    "total_revenue_yoy_growth_ttm": "revenue_growth",
    "net_income_yoy_growth_ttm": "net_income_growth",
    "gross_margin": "gross_margin",
    "ebitda_margin_ttm": "ebitda_margin",
    "after_tax_margin": "net_margin",
    "return_on_equity": "roe",
    "return_on_assets": "roa",
    "return_on_invested_capital": "roic",
}


_RATIO_FIELDS: Mapping[str, str] = {
    "current_ratio": "current_ratio",
}


_SPOT_FIELDS: Mapping[str, str] = {
    "price_earnings_ttm": "pe",
    "price_book_fq": "price_to_book",
    "price_revenue_ttm": "price_to_sales",
    "enterprise_value_ebitda_current": "ev_to_ebitda",
}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null"}:
        return None
    return text


def normalize_tradingview_symbol(value: Any) -> str:
    text = _clean(value) or ""
    if ":" in text:
        text = text.rsplit(":", 1)[-1]
    return text.strip().upper()


def _basis_for_metric(metric: str, fiscal_period: str | None) -> str:
    if metric in {
        "revenue_growth",
        "net_income_growth",
        "gross_margin",
        "ebitda_margin",
        "net_margin",
        "roe",
        "roa",
        "roic",
    }:
        return "TRADINGVIEW_TTM"
    if metric == "current_ratio":
        return f"TRADINGVIEW_MRQ:{fiscal_period or 'UNKNOWN'}"
    if metric == "price_to_book":
        return f"TRADINGVIEW_SPOT_MRQ:{fiscal_period or 'UNKNOWN'}"
    return "TRADINGVIEW_SPOT_TTM"


def tradingview_row_to_observation(row: Mapping[str, Any]) -> PeerObservation | None:
    symbol = normalize_tradingview_symbol(row.get("name") or row.get("ticker") or row.get("symbol"))
    if not symbol:
        return None

    sector = _clean(row.get("sector"))
    industry = _clean(row.get("industry"))
    classification: CompanyClassification = classify_company(
        symbol=symbol,
        sector=sector,
        industry=industry,
        source="TradingView Screener",
    )
    fiscal_period = _clean(row.get("fiscal_period_current"))

    metrics: dict[str, float] = {}
    metric_basis: dict[str, str] = {}

    for provider_name, metric_name in _PERCENT_FIELDS.items():
        raw = _finite(row.get(provider_name))
        if raw is None:
            continue
        metrics[metric_name] = raw / 100.0
        metric_basis[metric_name] = _basis_for_metric(metric_name, fiscal_period)

    for provider_name, metric_name in _RATIO_FIELDS.items():
        raw = _finite(row.get(provider_name))
        if raw is None:
            continue
        metrics[metric_name] = raw
        metric_basis[metric_name] = _basis_for_metric(metric_name, fiscal_period)

    for provider_name, metric_name in _SPOT_FIELDS.items():
        raw = _finite(row.get(provider_name))
        if raw is None or raw <= 0:
            # Negative P/E or other non-positive valuation multiples are not
            # ranked as "cheap"; absence is safer than a misleading ordinal.
            continue
        metrics[metric_name] = raw
        metric_basis[metric_name] = _basis_for_metric(metric_name, fiscal_period)

    return PeerObservation(
        symbol=symbol,
        peer_group=classification.peer_group,
        sector_type=classification.sector_type,
        metrics=metrics,
        metric_basis=metric_basis,
        metadata={
            "provider": "TradingView Screener",
            "company_name": _clean(row.get("description")),
            "sector": sector,
            "industry": industry,
            "classification_confidence": classification.confidence,
            "classification_metadata": dict(classification.metadata),
            "market_cap_basic": _finite(row.get("market_cap_basic")),
            "fiscal_period_current": fiscal_period,
            "fiscal_period_end_current": _clean(row.get("fiscal_period_end_current")),
        },
    )


def observations_from_tradingview_rows(
    rows: Iterable[Mapping[str, Any]],
) -> list[PeerObservation]:
    observations: list[PeerObservation] = []
    seen_symbols: set[str] = set()
    for row in rows:
        observation = tradingview_row_to_observation(row)
        if observation is None or observation.symbol in seen_symbols:
            continue
        seen_symbols.add(observation.symbol)
        observations.append(observation)
    return observations


def observations_from_tradingview_frame(frame: pd.DataFrame) -> list[PeerObservation]:
    if frame.empty:
        return []
    return observations_from_tradingview_rows(frame.to_dict(orient="records"))


def tradingview_classification_from_frame(
    frame: pd.DataFrame,
    symbol: str,
) -> CompanyClassification | None:
    normalized = symbol.strip().upper()
    if not normalized or frame.empty:
        return None
    for row in frame.to_dict(orient="records"):
        if normalize_tradingview_symbol(row.get("name")) != normalized:
            continue
        return classify_company(
            symbol=normalized,
            sector=_clean(row.get("sector")),
            industry=_clean(row.get("industry")),
            source="TradingView Screener",
        )
    return None


__all__ = [
    "TRADINGVIEW_FIELDS",
    "normalize_tradingview_symbol",
    "observations_from_tradingview_frame",
    "observations_from_tradingview_rows",
    "tradingview_classification_from_frame",
    "tradingview_row_to_observation",
]
