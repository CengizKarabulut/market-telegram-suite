from __future__ import annotations

import math
from typing import Any, Mapping

from .fundamental_metrics import MetricResult, OK
from .valuation import ValuationState


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _put(
    metrics: dict[str, float],
    basis: dict[str, str],
    name: str,
    value: Any,
    metric_basis: str,
    *,
    overwrite: bool = False,
) -> None:
    numeric = _finite(value)
    if numeric is None:
        return
    if not overwrite and name in metrics:
        return
    metrics[name] = numeric
    basis[name] = metric_basis


def _from_metric_results(
    metrics: dict[str, float],
    basis: dict[str, str],
    values: Mapping[str, Any],
    metric_basis: str,
) -> None:
    for name, raw in values.items():
        if isinstance(raw, MetricResult) and raw.status == OK:
            _put(metrics, basis, name, raw.value, metric_basis)


def peer_metrics_from_states(
    *,
    fundamental_state: Mapping[str, Any] | None = None,
    current_period_view: Mapping[str, Any] | None = None,
    valuation_state: ValuationState | None = None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Flatten canonical states into comparable peer metrics with basis labels.

    TTM metrics are preferred over current-YTD fallbacks. Valuation metrics are
    explicitly marked price-sensitive. The benchmark engine can then exclude
    peers whose metric basis differs from the target instead of mixing TTM,
    YTD and spot valuation values in one distribution.
    """
    metrics: dict[str, float] = {}
    basis: dict[str, str] = {}

    if fundamental_state:
        ttm_method = str(fundamental_state.get("ttm_method") or "TTM").strip() or "TTM"
        ttm_basis = f"TTM:{ttm_method}"
        _from_metric_results(
            metrics,
            basis,
            fundamental_state.get("metrics") or {},
            ttm_basis,
        )
        _from_metric_results(
            metrics,
            basis,
            fundamental_state.get("sector_metrics") or {},
            ttm_basis,
        )

    if current_period_view and current_period_view.get("available"):
        period_end = current_period_view.get("period_end")
        period_label = getattr(period_end, "date", lambda: period_end)()
        current_basis = f"CURRENT_REPORT:{period_label}"
        current = current_period_view.get("current_period") or {}
        balance = current_period_view.get("balance") or {}
        comparative = current_period_view.get("comparative") or {}

        _put(
            metrics,
            basis,
            "operating_cash_flow_to_net_income",
            current.get("operating_cash_flow_to_net_income"),
            current_basis,
        )
        _put(metrics, basis, "ltv", balance.get("ltv"), current_basis)
        _put(metrics, basis, "current_ratio", balance.get("current_ratio"), current_basis)
        _put(
            metrics,
            basis,
            "financial_debt_to_equity",
            balance.get("financial_debt_to_equity"),
            current_basis,
        )

        if comparative.get("available"):
            comp_label = str(comparative.get("label") or "COMPARATIVE")
            comparison_basis = f"CURRENT_PROVIDER_COMPARATIVE:{comp_label}"
            for name in ("revenue_growth", "net_income_growth"):
                growth = comparative.get(name) or {}
                if growth.get("status") == "OK":
                    _put(metrics, basis, name, growth.get("value"), comparison_basis)

    if valuation_state is not None and valuation_state.available:
        spot_basis = "SPOT_VALUATION"
        _from_metric_results(metrics, basis, valuation_state.multiples, spot_basis)
        _from_metric_results(metrics, basis, valuation_state.sector_metrics, spot_basis)
        pb = valuation_state.multiples.get("pb")
        if isinstance(pb, MetricResult) and pb.status == OK:
            _put(metrics, basis, "price_to_book", pb.value, spot_basis)

    return metrics, basis


__all__ = ["peer_metrics_from_states"]
