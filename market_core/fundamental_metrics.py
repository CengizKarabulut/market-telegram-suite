from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .fundamental_models import FinancialSnapshot, SectorType
from .ttm import TTMResult


@dataclass(frozen=True)
class MetricResult:
    name: str
    status: str
    value: float | None = None
    unit: str | None = None
    basis: str | None = None
    reason: str | None = None
    inputs: dict[str, float | None] = field(default_factory=dict)


OK = "OK"
UNAVAILABLE = "UNAVAILABLE"
NOT_MEANINGFUL = "NOT_MEANINGFUL"


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _metric(
    name: str,
    *,
    value: float | None,
    unit: str | None = None,
    basis: str | None = None,
    status: str = OK,
    reason: str | None = None,
    inputs: dict[str, float | None] | None = None,
) -> MetricResult:
    return MetricResult(
        name=name,
        status=status,
        value=value,
        unit=unit,
        basis=basis,
        reason=reason,
        inputs=dict(inputs or {}),
    )


def _unavailable(name: str, reason: str, *, unit: str | None = None) -> MetricResult:
    return _metric(name, value=None, unit=unit, status=UNAVAILABLE, reason=reason)


def _not_meaningful(
    name: str,
    reason: str,
    *,
    unit: str | None = None,
    inputs: dict[str, float | None] | None = None,
) -> MetricResult:
    return _metric(
        name,
        value=None,
        unit=unit,
        status=NOT_MEANINGFUL,
        reason=reason,
        inputs=inputs,
    )


def _amount(snapshot: FinancialSnapshot, block: str, key: str) -> float | None:
    raw = getattr(snapshot, block).get(key)
    value = _finite(raw)
    return value * snapshot.scale if value is not None else None


def _ttm_value(ttm: TTMResult, block: str, key: str) -> float | None:
    values = getattr(ttm, block)
    return _finite(values.get(key))


def _ratio_metric(
    name: str,
    numerator: float | None,
    denominator: float | None,
    *,
    denominator_must_be_positive: bool = True,
    unit: str = "ratio",
    basis: str | None = None,
) -> MetricResult:
    if numerator is None or denominator is None:
        return _unavailable(name, "Gerekli finansal kalemlerden biri eksik.", unit=unit)
    if denominator_must_be_positive and denominator <= 0:
        return _not_meaningful(
            name,
            "Payda sıfır veya negatif olduğu için oran anlamlı değil.",
            unit=unit,
            inputs={"numerator": numerator, "denominator": denominator},
        )
    if not denominator_must_be_positive and denominator == 0:
        return _not_meaningful(
            name,
            "Payda sıfır olduğu için oran anlamlı değil.",
            unit=unit,
            inputs={"numerator": numerator, "denominator": denominator},
        )
    return _metric(
        name,
        value=numerator / denominator,
        unit=unit,
        basis=basis,
        inputs={"numerator": numerator, "denominator": denominator},
    )


def _total_debt(snapshot: FinancialSnapshot) -> float | None:
    direct = _amount(snapshot, "balance_sheet", "total_financial_debt")
    if direct is not None:
        return direct
    short = _amount(snapshot, "balance_sheet", "short_term_financial_debt")
    long = _amount(snapshot, "balance_sheet", "long_term_financial_debt")
    if short is None or long is None:
        return None
    return short + long


def _cash(snapshot: FinancialSnapshot) -> float | None:
    value = _amount(snapshot, "balance_sheet", "cash_and_equivalents")
    if value is not None:
        return value
    return _amount(snapshot, "balance_sheet", "cash_and_cash_equivalents")


def _net_debt(snapshot: FinancialSnapshot) -> float | None:
    debt = _total_debt(snapshot)
    cash = _cash(snapshot)
    if debt is None or cash is None:
        return None
    return debt - cash


def _compatible_balance_pair(current: FinancialSnapshot, prior: FinancialSnapshot | None) -> bool:
    if prior is None:
        return False
    return (
        current.symbol.strip().upper() == prior.symbol.strip().upper()
        and current.currency.strip().upper() == prior.currency.strip().upper()
        and str(current.inflation_accounting or "").strip().upper()
        == str(prior.inflation_accounting or "").strip().upper()
    )


def _average_balance_metric(
    name: str,
    earnings: float | None,
    current: FinancialSnapshot,
    prior: FinancialSnapshot | None,
    key: str,
) -> MetricResult:
    if not _compatible_balance_pair(current, prior):
        return _unavailable(
            name,
            "Ortalama bilanço paydası için uyumlu önceki dönem snapshot'ı yok.",
            unit="ratio",
        )
    assert prior is not None
    current_value = _amount(current, "balance_sheet", key)
    prior_value = _amount(prior, "balance_sheet", key)
    if current_value is None or prior_value is None or earnings is None:
        return _unavailable(name, "Gerekli finansal kalemlerden biri eksik.", unit="ratio")
    average = (current_value + prior_value) / 2.0
    return _ratio_metric(
        name,
        earnings,
        average,
        denominator_must_be_positive=True,
        unit="ratio",
        basis="AVERAGE_BALANCE",
    )


def _free_cash_flow(ttm: TTMResult) -> MetricResult:
    ocf = _ttm_value(ttm, "cash_flow", "operating_cash_flow")
    capex = _ttm_value(ttm, "cash_flow", "capital_expenditures")
    if ocf is None or capex is None:
        return _unavailable(
            "free_cash_flow",
            "Operasyonel nakit akışı veya yatırım harcaması eksik.",
            unit="currency",
        )
    return _metric(
        "free_cash_flow",
        value=ocf - capex,
        unit="currency",
        basis="OCF_MINUS_CAPEX_POSITIVE_OUTFLOW",
        inputs={"operating_cash_flow": ocf, "capital_expenditures": capex},
    )


def _growth_metric(name: str, current: float | None, prior: float | None) -> MetricResult:
    if current is None or prior is None:
        return _unavailable(name, "Cari veya karşılaştırmalı TTM değeri eksik.", unit="ratio")
    if prior <= 0:
        return _not_meaningful(
            name,
            "Karşılaştırma dönemi sıfır veya negatif olduğu için büyüme oranı anlamlı değil.",
            unit="ratio",
            inputs={"current": current, "prior": prior},
        )
    return _metric(
        name,
        value=current / prior - 1.0,
        unit="ratio",
        basis="TTM_VS_PRIOR_TTM",
        inputs={"current": current, "prior": prior},
    )


def _effective_tax_rate(ttm: TTMResult) -> float | None:
    pretax = _ttm_value(ttm, "income_statement", "profit_before_tax")
    tax = _ttm_value(ttm, "income_statement", "tax_expense")
    if pretax is None or tax is None or pretax <= 0 or tax < 0:
        return None
    rate = tax / pretax
    if not 0 <= rate <= 1:
        return None
    return rate


def _roic(
    snapshot: FinancialSnapshot,
    prior_snapshot: FinancialSnapshot | None,
    ttm: TTMResult,
) -> MetricResult:
    ebit = _ttm_value(ttm, "income_statement", "ebit")
    tax_rate = _effective_tax_rate(ttm)
    if ebit is None or tax_rate is None:
        return _unavailable(
            "roic",
            "EBIT veya güvenilir efektif vergi oranı eksik.",
            unit="ratio",
        )
    if not _compatible_balance_pair(snapshot, prior_snapshot):
        return _unavailable(
            "roic",
            "Ortalama yatırılmış sermaye için uyumlu önceki dönem snapshot'ı yok.",
            unit="ratio",
        )
    assert prior_snapshot is not None
    current_equity = _amount(snapshot, "balance_sheet", "equity")
    prior_equity = _amount(prior_snapshot, "balance_sheet", "equity")
    current_net_debt = _net_debt(snapshot)
    prior_net_debt = _net_debt(prior_snapshot)
    if None in {current_equity, prior_equity, current_net_debt, prior_net_debt}:
        return _unavailable("roic", "Özkaynak veya net borç kalemleri eksik.", unit="ratio")
    current_invested = float(current_equity) + float(current_net_debt)
    prior_invested = float(prior_equity) + float(prior_net_debt)
    average_invested = (current_invested + prior_invested) / 2.0
    nopat = ebit * (1.0 - tax_rate)
    return _ratio_metric(
        "roic",
        nopat,
        average_invested,
        denominator_must_be_positive=True,
        unit="ratio",
        basis="NOPAT_OVER_AVERAGE_EQUITY_PLUS_NET_DEBT",
    )


def _working_capital_change(
    snapshot: FinancialSnapshot,
    prior_snapshot: FinancialSnapshot | None,
) -> MetricResult:
    if not _compatible_balance_pair(snapshot, prior_snapshot):
        return _unavailable(
            "working_capital_change",
            "Karşılaştırılabilir önceki bilanço yok.",
            unit="currency",
        )
    assert prior_snapshot is not None
    current_assets = _amount(snapshot, "balance_sheet", "current_assets")
    current_liabilities = _amount(snapshot, "balance_sheet", "current_liabilities")
    prior_assets = _amount(prior_snapshot, "balance_sheet", "current_assets")
    prior_liabilities = _amount(prior_snapshot, "balance_sheet", "current_liabilities")
    if None in {current_assets, current_liabilities, prior_assets, prior_liabilities}:
        return _unavailable(
            "working_capital_change",
            "Dönen varlık veya kısa vadeli yükümlülük kalemi eksik.",
            unit="currency",
        )
    current_wc = float(current_assets) - float(current_liabilities)
    prior_wc = float(prior_assets) - float(prior_liabilities)
    return _metric(
        "working_capital_change",
        value=current_wc - prior_wc,
        unit="currency",
        basis="CURRENT_NWC_MINUS_PRIOR_NWC",
        inputs={"current_nwc": current_wc, "prior_nwc": prior_wc},
    )


def _gyo_metrics(snapshot: FinancialSnapshot, ttm: TTMResult, net_debt: float | None) -> dict[str, MetricResult]:
    portfolio = _amount(snapshot, "balance_sheet", "investment_property_fair_value")
    if portfolio is None:
        portfolio = _finite(snapshot.metadata.get("portfolio_value"))
        if portfolio is not None:
            portfolio *= snapshot.scale

    nav_raw = snapshot.metadata.get("nav_value")
    nav = _finite(nav_raw)
    if nav is not None:
        nav *= snapshot.scale

    rental_revenue = _ttm_value(ttm, "income_statement", "rental_revenue")
    revenue = _ttm_value(ttm, "income_statement", "revenue")
    fair_value_gain = _ttm_value(ttm, "income_statement", "fair_value_gain_investment_property")
    pretax = _ttm_value(ttm, "income_statement", "profit_before_tax")

    return {
        "ltv": _ratio_metric(
            "ltv",
            net_debt,
            portfolio,
            denominator_must_be_positive=True,
            unit="ratio",
            basis="NET_DEBT_OVER_INVESTMENT_PROPERTY_FAIR_VALUE",
        ),
        "rental_revenue_share": _ratio_metric(
            "rental_revenue_share",
            rental_revenue,
            revenue,
            denominator_must_be_positive=True,
            unit="ratio",
            basis="RENTAL_REVENUE_OVER_TOTAL_REVENUE",
        ),
        "fair_value_gain_share_of_pretax": _ratio_metric(
            "fair_value_gain_share_of_pretax",
            fair_value_gain,
            pretax,
            denominator_must_be_positive=True,
            unit="ratio",
            basis="FAIR_VALUE_GAIN_OVER_PRETAX_PROFIT",
        ),
        "reported_nav": (
            _metric(
                "reported_nav",
                value=nav,
                unit="currency",
                basis="EXPLICIT_PROVIDER_NAV",
            )
            if nav is not None
            else _unavailable(
                "reported_nav",
                "Güvenilir NAV verisi sağlanmamış; özkaynak NAV yerine kullanılmaz.",
                unit="currency",
            )
        ),
    }


def build_fundamental_metrics(
    snapshot: FinancialSnapshot,
    ttm: TTMResult,
    *,
    prior_snapshot: FinancialSnapshot | None = None,
    prior_ttm: TTMResult | None = None,
) -> dict[str, Any]:
    """Canonical finansallardan deterministic temel metrikler üretir.

    Core, provider alan adlarını tahmin etmez. Adapter'lar ``revenue``, ``ebitda``,
    ``equity`` gibi canonical anahtarları üretmelidir. Negatif/anlamsız paydalarda
    oran fail-closed biçimde ``NOT_MEANINGFUL`` döner.
    """
    if not ttm.available:
        return {
            "available": False,
            "reason": f"TTM kullanılamıyor: {ttm.reason or 'neden belirtilmedi'}",
            "metrics": {},
            "sector_metrics": {},
        }
    if snapshot.symbol.strip().upper() != ttm.symbol.strip().upper():
        return {
            "available": False,
            "reason": "Snapshot ve TTM sembolleri eşleşmiyor.",
            "metrics": {},
            "sector_metrics": {},
        }
    if snapshot.currency.strip().upper() != str(ttm.currency or "").strip().upper():
        return {
            "available": False,
            "reason": "Snapshot ve TTM para birimleri eşleşmiyor.",
            "metrics": {},
            "sector_metrics": {},
        }

    revenue = _ttm_value(ttm, "income_statement", "revenue")
    gross_profit = _ttm_value(ttm, "income_statement", "gross_profit")
    ebitda = _ttm_value(ttm, "income_statement", "ebitda")
    ebit = _ttm_value(ttm, "income_statement", "ebit")
    net_income = _ttm_value(ttm, "income_statement", "net_income")
    interest_expense = _ttm_value(ttm, "income_statement", "interest_expense")
    ocf = _ttm_value(ttm, "cash_flow", "operating_cash_flow")
    equity = _amount(snapshot, "balance_sheet", "equity")
    assets = _amount(snapshot, "balance_sheet", "total_assets")
    net_debt = _net_debt(snapshot)

    prior_revenue = (
        _ttm_value(prior_ttm, "income_statement", "revenue")
        if prior_ttm is not None and prior_ttm.available
        else None
    )
    prior_net_income = (
        _ttm_value(prior_ttm, "income_statement", "net_income")
        if prior_ttm is not None and prior_ttm.available
        else None
    )

    fcf = _free_cash_flow(ttm)
    metrics: dict[str, MetricResult] = {
        "revenue_growth": _growth_metric("revenue_growth", revenue, prior_revenue),
        "net_income_growth": _growth_metric("net_income_growth", net_income, prior_net_income),
        "gross_margin": _ratio_metric("gross_margin", gross_profit, revenue, unit="ratio"),
        "ebitda_margin": _ratio_metric("ebitda_margin", ebitda, revenue, unit="ratio"),
        "net_margin": _ratio_metric("net_margin", net_income, revenue, unit="ratio"),
        "roe": _average_balance_metric("roe", net_income, snapshot, prior_snapshot, "equity"),
        "roa": _average_balance_metric("roa", net_income, snapshot, prior_snapshot, "total_assets"),
        "roic": _roic(snapshot, prior_snapshot, ttm),
        "net_debt": (
            _metric("net_debt", value=net_debt, unit="currency", basis="FINANCIAL_DEBT_MINUS_CASH")
            if net_debt is not None
            else _unavailable("net_debt", "Finansal borç veya nakit kalemi eksik.", unit="currency")
        ),
        "net_debt_to_ebitda": _ratio_metric(
            "net_debt_to_ebitda",
            net_debt,
            ebitda,
            denominator_must_be_positive=True,
            unit="ratio",
        ),
        "interest_coverage": _ratio_metric(
            "interest_coverage",
            ebit,
            interest_expense,
            denominator_must_be_positive=True,
            unit="ratio",
            basis="EBIT_OVER_INTEREST_EXPENSE",
        ),
        "operating_cash_flow_to_net_income": _ratio_metric(
            "operating_cash_flow_to_net_income",
            ocf,
            net_income,
            denominator_must_be_positive=True,
            unit="ratio",
        ),
        "free_cash_flow": fcf,
        "working_capital_change": _working_capital_change(snapshot, prior_snapshot),
        "equity": (
            _metric("equity", value=equity, unit="currency")
            if equity is not None
            else _unavailable("equity", "Özkaynak kalemi eksik.", unit="currency")
        ),
        "total_assets": (
            _metric("total_assets", value=assets, unit="currency")
            if assets is not None
            else _unavailable("total_assets", "Toplam varlık kalemi eksik.", unit="currency")
        ),
    }

    sector_metrics: dict[str, MetricResult] = {}
    if snapshot.sector_type == SectorType.GYO:
        sector_metrics = _gyo_metrics(snapshot, ttm, net_debt)

    return {
        "available": True,
        "symbol": snapshot.symbol,
        "sector_type": snapshot.sector_type.value,
        "period_end": snapshot.period_end,
        "published_at": snapshot.published_at,
        "currency": snapshot.currency,
        "ttm_method": ttm.method,
        "metrics": metrics,
        "sector_metrics": sector_metrics,
        "quality": {
            "point_in_time": bool(ttm.quality.get("point_in_time")),
            "uses_average_balance_for_roe_roa": True,
            "capex_semantics": "positive_cash_outflow",
            "nav_is_never_derived_from_equity": True,
        },
    }
