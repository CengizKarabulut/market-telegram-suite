from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .fundamental_metrics import MetricResult, NOT_MEANINGFUL, OK, UNAVAILABLE
from .fundamental_models import FinancialSnapshot, SectorType
from .ttm import TTMResult


@dataclass(frozen=True)
class ValuationState:
    symbol: str
    price: float
    currency: str
    available: bool
    market_cap: MetricResult
    enterprise_value: MetricResult
    multiples: dict[str, MetricResult] = field(default_factory=dict)
    sector_metrics: dict[str, MetricResult] = field(default_factory=dict)
    reason: str | None = None
    quality: dict[str, Any] = field(default_factory=dict)


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
    value = _finite(getattr(snapshot, block).get(key))
    return value * snapshot.scale if value is not None else None


def _ttm_value(ttm: TTMResult, block: str, key: str) -> float | None:
    return _finite(getattr(ttm, block).get(key))


def _fundamental_metric(
    fundamental_state: dict[str, Any] | None,
    name: str,
    *,
    sector: bool = False,
) -> MetricResult | None:
    if not fundamental_state:
        return None
    family = "sector_metrics" if sector else "metrics"
    value = (fundamental_state.get(family) or {}).get(name)
    return value if isinstance(value, MetricResult) else None


def _positive_denominator_multiple(
    name: str,
    numerator: float | None,
    denominator: float | None,
    *,
    basis: str,
) -> MetricResult:
    if numerator is None or denominator is None:
        return _unavailable(name, "Değerleme için gerekli kalemlerden biri eksik.", unit="multiple")
    if numerator <= 0:
        return _unavailable(name, "Değerleme payı pozitif değil.", unit="multiple")
    if denominator <= 0:
        return _not_meaningful(
            name,
            "Payda sıfır veya negatif olduğu için çarpan anlamlı değil.",
            unit="multiple",
            inputs={"numerator": numerator, "denominator": denominator},
        )
    return _metric(
        name,
        value=numerator / denominator,
        unit="multiple",
        basis=basis,
        inputs={"numerator": numerator, "denominator": denominator},
    )


def _yield_metric(name: str, numerator: float | None, market_cap: float | None) -> MetricResult:
    if numerator is None or market_cap is None:
        return _unavailable(name, "Getiri oranı için gerekli kalemlerden biri eksik.", unit="ratio")
    if market_cap <= 0:
        return _unavailable(name, "Piyasa değeri pozitif değil.", unit="ratio")
    return _metric(
        name,
        value=numerator / market_cap,
        unit="ratio",
        basis="TTM_AMOUNT_OVER_MARKET_CAP",
        inputs={"numerator": numerator, "market_cap": market_cap},
    )


def build_daily_valuation(
    snapshot: FinancialSnapshot,
    ttm: TTMResult,
    *,
    price: float,
    price_currency: str,
    fundamental_state: dict[str, Any] | None = None,
) -> ValuationState:
    """Aynı finansal snapshot üzerinde fiyat değiştikçe günlük değerlemeyi yeniler.

    Bu katman sabit ucuz/pahalı eşiği üretmez. Yalnız hesaplanabilir çarpanları
    canonical biçimde verir; tarihsel/peer bağlam sonraki katmanın işidir.
    GYO NAV metriği yalnız açıkça sağlanan NAV verisine dayanır, özkaynak hiçbir
    durumda NAV yerine geçirilmez.
    """
    normalized_currency = price_currency.strip().upper()
    numeric_price = _finite(price)
    unavailable_market_cap = _unavailable("market_cap", "Piyasa değeri hesaplanamadı.", unit="currency")
    unavailable_ev = _unavailable("enterprise_value", "Firma değeri hesaplanamadı.", unit="currency")

    if numeric_price is None or numeric_price <= 0:
        return ValuationState(
            symbol=snapshot.symbol,
            price=float(price) if _finite(price) is not None else math.nan,
            currency=normalized_currency,
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="Fiyat pozitif ve sonlu olmalıdır.",
        )
    if not normalized_currency:
        return ValuationState(
            symbol=snapshot.symbol,
            price=numeric_price,
            currency="",
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="Fiyat para birimi belirtilmelidir.",
        )
    if normalized_currency != snapshot.currency.strip().upper():
        return ValuationState(
            symbol=snapshot.symbol,
            price=numeric_price,
            currency=normalized_currency,
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="Fiyat ve finansal snapshot para birimleri eşleşmiyor.",
        )
    if not ttm.available or ttm.symbol.strip().upper() != snapshot.symbol.strip().upper():
        return ValuationState(
            symbol=snapshot.symbol,
            price=numeric_price,
            currency=normalized_currency,
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="Uyumlu ve kullanılabilir TTM verisi yok.",
        )
    if str(ttm.currency or "").strip().upper() != normalized_currency:
        return ValuationState(
            symbol=snapshot.symbol,
            price=numeric_price,
            currency=normalized_currency,
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="TTM ve fiyat para birimleri eşleşmiyor.",
        )

    shares = _finite(snapshot.shares_outstanding)
    if shares is None or shares <= 0:
        return ValuationState(
            symbol=snapshot.symbol,
            price=numeric_price,
            currency=normalized_currency,
            available=False,
            market_cap=unavailable_market_cap,
            enterprise_value=unavailable_ev,
            reason="Geçerli pay sayısı olmadan piyasa değeri hesaplanamaz.",
        )

    market_cap_value = numeric_price * shares
    market_cap = _metric(
        "market_cap",
        value=market_cap_value,
        unit="currency",
        basis="PRICE_TIMES_SHARES_OUTSTANDING",
        inputs={"price": numeric_price, "shares_outstanding": shares},
    )

    net_debt_metric = _fundamental_metric(fundamental_state, "net_debt")
    net_debt = (
        _finite(net_debt_metric.value)
        if net_debt_metric is not None and net_debt_metric.status == OK
        else None
    )
    if net_debt is None:
        debt = _amount(snapshot, "balance_sheet", "total_financial_debt")
        if debt is None:
            short = _amount(snapshot, "balance_sheet", "short_term_financial_debt")
            long = _amount(snapshot, "balance_sheet", "long_term_financial_debt")
            debt = short + long if short is not None and long is not None else None
        cash = _amount(snapshot, "balance_sheet", "cash_and_equivalents")
        if cash is None:
            cash = _amount(snapshot, "balance_sheet", "cash_and_cash_equivalents")
        net_debt = debt - cash if debt is not None and cash is not None else None

    if net_debt is None:
        enterprise_value = _unavailable(
            "enterprise_value",
            "Net borç hesaplanamadığı için firma değeri üretilemedi.",
            unit="currency",
        )
        enterprise_value_value = None
    else:
        enterprise_value_value = market_cap_value + net_debt
        enterprise_value = _metric(
            "enterprise_value",
            value=enterprise_value_value,
            unit="currency",
            basis="MARKET_CAP_PLUS_NET_DEBT",
            inputs={"market_cap": market_cap_value, "net_debt": net_debt},
        )

    net_income = _ttm_value(ttm, "income_statement", "net_income")
    revenue = _ttm_value(ttm, "income_statement", "revenue")
    ebitda = _ttm_value(ttm, "income_statement", "ebitda")
    equity = _amount(snapshot, "balance_sheet", "equity")

    fcf_metric = _fundamental_metric(fundamental_state, "free_cash_flow")
    fcf = (
        _finite(fcf_metric.value)
        if fcf_metric is not None and fcf_metric.status == OK
        else None
    )
    if fcf is None:
        ocf = _ttm_value(ttm, "cash_flow", "operating_cash_flow")
        capex = _ttm_value(ttm, "cash_flow", "capital_expenditures")
        fcf = ocf - capex if ocf is not None and capex is not None else None

    multiples = {
        "pe": _positive_denominator_multiple(
            "pe",
            market_cap_value,
            net_income,
            basis="MARKET_CAP_OVER_TTM_NET_INCOME",
        ),
        "pb": _positive_denominator_multiple(
            "pb",
            market_cap_value,
            equity,
            basis="MARKET_CAP_OVER_EQUITY",
        ),
        "ps": _positive_denominator_multiple(
            "ps",
            market_cap_value,
            revenue,
            basis="MARKET_CAP_OVER_TTM_REVENUE",
        ),
        "ev_to_ebitda": _positive_denominator_multiple(
            "ev_to_ebitda",
            enterprise_value_value,
            ebitda,
            basis="ENTERPRISE_VALUE_OVER_TTM_EBITDA",
        ),
        "fcf_yield": _yield_metric("fcf_yield", fcf, market_cap_value),
    }

    sector_metrics: dict[str, MetricResult] = {}
    if snapshot.sector_type == SectorType.GYO:
        nav_metric = _fundamental_metric(fundamental_state, "reported_nav", sector=True)
        nav = (
            _finite(nav_metric.value)
            if nav_metric is not None and nav_metric.status == OK
            else None
        )
        if nav is None:
            nav_raw = _finite(snapshot.metadata.get("nav_value"))
            nav = nav_raw * snapshot.scale if nav_raw is not None else None
        if nav is None:
            sector_metrics["price_to_nav"] = _unavailable(
                "price_to_nav",
                "Güvenilir NAV sağlanmadığı için P/NAV hesaplanmadı; özkaynak NAV değildir.",
                unit="multiple",
            )
            sector_metrics["nav_discount"] = _unavailable(
                "nav_discount",
                "Güvenilir NAV sağlanmadığı için NAV iskontosu hesaplanmadı; özkaynak NAV değildir.",
                unit="ratio",
            )
        elif nav <= 0:
            sector_metrics["price_to_nav"] = _not_meaningful(
                "price_to_nav",
                "NAV pozitif olmadığı için P/NAV anlamlı değil.",
                unit="multiple",
            )
            sector_metrics["nav_discount"] = _not_meaningful(
                "nav_discount",
                "NAV pozitif olmadığı için iskonto/primi anlamlı değil.",
                unit="ratio",
            )
        else:
            price_to_nav = market_cap_value / nav
            sector_metrics["price_to_nav"] = _metric(
                "price_to_nav",
                value=price_to_nav,
                unit="multiple",
                basis="MARKET_CAP_OVER_EXPLICIT_NAV",
                inputs={"market_cap": market_cap_value, "nav": nav},
            )
            sector_metrics["nav_discount"] = _metric(
                "nav_discount",
                value=1.0 - price_to_nav,
                unit="ratio",
                basis="ONE_MINUS_MARKET_CAP_OVER_EXPLICIT_NAV",
                inputs={"market_cap": market_cap_value, "nav": nav},
            )

    return ValuationState(
        symbol=snapshot.symbol,
        price=numeric_price,
        currency=normalized_currency,
        available=True,
        market_cap=market_cap,
        enterprise_value=enterprise_value,
        multiples=multiples,
        sector_metrics=sector_metrics,
        quality={
            "point_in_time_financials": bool(ttm.quality.get("point_in_time")),
            "price_sensitive": True,
            "fixed_cheap_expensive_thresholds": False,
            "nav_is_never_derived_from_equity": True,
        },
    )
