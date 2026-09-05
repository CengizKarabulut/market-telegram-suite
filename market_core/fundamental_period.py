from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping

from .fundamental_models import FinancialSnapshot, SectorType


@dataclass(frozen=True)
class PeriodComparative:
    """Canonical comparative values visible in the current reporting context.

    A comparative is not a historical point-in-time snapshot unless an exact
    historical ``published_at`` is independently known. This type is therefore
    used only for current-report comparisons such as YoY YTD growth; it must not
    be fed into point-in-time backtests or TTM assembly as a synthetic filing.
    """

    label: str
    currency: str
    scale: float
    basis: str
    income_statement: Mapping[str, float | None] = field(default_factory=dict)
    balance_sheet: Mapping[str, float | None] = field(default_factory=dict)
    cash_flow: Mapping[str, float | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("PeriodComparative label boş olamaz.")
        if not self.currency.strip():
            raise ValueError("PeriodComparative currency boş olamaz.")
        if self.scale <= 0:
            raise ValueError("PeriodComparative scale pozitif olmalıdır.")
        if not self.basis.strip():
            raise ValueError("PeriodComparative basis boş olamaz.")


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _amount(values: Mapping[str, float | None], key: str, scale: float) -> float | None:
    value = _finite(values.get(key))
    return value * scale if value is not None else None


def _snapshot_amount(snapshot: FinancialSnapshot, block: str, key: str) -> float | None:
    return _amount(getattr(snapshot, block), key, snapshot.scale)


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _growth(current: float | None, prior: float | None) -> dict[str, Any]:
    if current is None or prior is None:
        return {"status": "UNAVAILABLE", "value": None}
    if prior <= 0:
        return {
            "status": "NOT_MEANINGFUL",
            "value": None,
            "reason": "Karşılaştırma dönemi sıfır veya negatif.",
            "current": current,
            "prior": prior,
        }
    return {
        "status": "OK",
        "value": current / prior - 1.0,
        "current": current,
        "prior": prior,
    }


def _financial_debt(snapshot: FinancialSnapshot) -> float | None:
    direct = _snapshot_amount(snapshot, "balance_sheet", "total_financial_debt")
    if direct is not None:
        return direct
    short = _snapshot_amount(snapshot, "balance_sheet", "short_term_financial_debt")
    long = _snapshot_amount(snapshot, "balance_sheet", "long_term_financial_debt")
    if short is None or long is None:
        return None
    return short + long


def _balance_view(snapshot: FinancialSnapshot) -> dict[str, Any]:
    debt = _financial_debt(snapshot)
    cash = _snapshot_amount(snapshot, "balance_sheet", "cash_and_equivalents")
    equity = _snapshot_amount(snapshot, "balance_sheet", "equity")
    current_assets = _snapshot_amount(snapshot, "balance_sheet", "current_assets")
    current_liabilities = _snapshot_amount(snapshot, "balance_sheet", "current_liabilities")
    investment_property = _snapshot_amount(
        snapshot,
        "balance_sheet",
        "investment_property_fair_value",
    )
    net_debt = debt - cash if debt is not None and cash is not None else None
    debt_to_equity = _ratio(debt, equity)
    current_ratio = _ratio(current_assets, current_liabilities)
    ltv = _ratio(net_debt, investment_property)

    leverage_state = "UNAVAILABLE"
    if ltv is not None:
        if ltv <= 0.20:
            leverage_state = "LOW"
        elif ltv <= 0.50:
            leverage_state = "MODERATE"
        else:
            leverage_state = "HIGH"

    return {
        "financial_debt": debt,
        "cash_and_equivalents": cash,
        "net_debt": net_debt,
        "equity": equity,
        "investment_property_fair_value": investment_property,
        "financial_debt_to_equity": debt_to_equity,
        "current_ratio": current_ratio,
        "ltv": ltv,
        "leverage_state": leverage_state,
    }


def _income_cash_view(snapshot: FinancialSnapshot) -> dict[str, Any]:
    revenue = _snapshot_amount(snapshot, "income_statement", "revenue")
    net_operating_profit = _snapshot_amount(
        snapshot,
        "income_statement",
        "net_operating_profit",
    )
    other_operating_income = _snapshot_amount(
        snapshot,
        "income_statement",
        "other_operating_income",
    )
    ebit = _snapshot_amount(snapshot, "income_statement", "ebit")
    net_income = _snapshot_amount(snapshot, "income_statement", "net_income")
    ocf = _snapshot_amount(snapshot, "cash_flow", "operating_cash_flow")

    cash_conversion_state = "UNAVAILABLE"
    if net_income is not None and ocf is not None:
        if net_income > 0 and ocf < 0:
            cash_conversion_state = "PROFIT_POSITIVE_CASH_FLOW_NEGATIVE"
        elif net_income > 0 and ocf >= 0:
            cash_conversion_state = "PROFIT_AND_CASH_FLOW_POSITIVE"
        elif net_income <= 0 and ocf < 0:
            cash_conversion_state = "PROFIT_AND_CASH_FLOW_WEAK"
        else:
            cash_conversion_state = "MIXED"

    other_income_state = "UNAVAILABLE"
    if other_operating_income is not None and revenue is not None:
        other_income_state = (
            "OTHER_OPERATING_INCOME_EXCEEDS_REVENUE"
            if abs(other_operating_income) > abs(revenue)
            else "OTHER_OPERATING_INCOME_WITHIN_REVENUE_SCALE"
        )

    operating_bridge_state = "UNAVAILABLE"
    if net_operating_profit is not None and ebit is not None:
        if net_operating_profit < 0 < ebit:
            operating_bridge_state = "CORE_OPERATING_NEGATIVE_REPORTED_OPERATING_POSITIVE"
        elif net_operating_profit >= 0 and ebit >= 0:
            operating_bridge_state = "BOTH_POSITIVE"
        elif net_operating_profit < 0 and ebit < 0:
            operating_bridge_state = "BOTH_NEGATIVE"
        else:
            operating_bridge_state = "MIXED"

    return {
        "revenue": revenue,
        "net_operating_profit": net_operating_profit,
        "other_operating_income": other_operating_income,
        "ebit": ebit,
        "net_income": net_income,
        "operating_cash_flow": ocf,
        "operating_cash_flow_to_net_income": _ratio(ocf, net_income),
        "other_operating_income_to_revenue": _ratio(other_operating_income, revenue),
        "other_operating_income_to_ebit": _ratio(other_operating_income, ebit),
        "cash_conversion_state": cash_conversion_state,
        "other_income_state": other_income_state,
        "operating_bridge_state": operating_bridge_state,
    }


def _comparative_view(
    snapshot: FinancialSnapshot,
    current: Mapping[str, Any],
    comparative: PeriodComparative | None,
) -> dict[str, Any]:
    if comparative is None:
        return {"available": False, "reason": "Karşılaştırmalı dönem sağlanmadı."}
    if comparative.currency.strip().upper() != snapshot.currency.strip().upper():
        return {"available": False, "reason": "Karşılaştırmalı dönemin para birimi uyumsuz."}

    prior_revenue = _amount(comparative.income_statement, "revenue", comparative.scale)
    prior_net_income = _amount(comparative.income_statement, "net_income", comparative.scale)
    prior_ocf = _amount(comparative.cash_flow, "operating_cash_flow", comparative.scale)
    current_ocf = _finite(current.get("operating_cash_flow"))

    return {
        "available": True,
        "label": comparative.label,
        "basis": comparative.basis,
        "historical_point_in_time": False,
        "revenue_growth": _growth(_finite(current.get("revenue")), prior_revenue),
        "net_income_growth": _growth(_finite(current.get("net_income")), prior_net_income),
        "operating_cash_flow_change": (
            current_ocf - prior_ocf
            if current_ocf is not None and prior_ocf is not None
            else None
        ),
        "prior_operating_cash_flow": prior_ocf,
    }


def _synthesis(
    snapshot: FinancialSnapshot,
    balance: Mapping[str, Any],
    current: Mapping[str, Any],
    comparative: Mapping[str, Any],
) -> dict[str, Any]:
    positives: list[str] = []
    risks: list[str] = []
    caveats: list[str] = []

    if balance.get("leverage_state") == "LOW":
        positives.append("Finansal kaldıraç, yatırım amaçlı gayrimenkul değerine göre düşük.")
    current_ratio = _finite(balance.get("current_ratio"))
    if current_ratio is not None and current_ratio >= 1.0:
        positives.append("Dönen varlıklar kısa vadeli yükümlülükleri karşılıyor.")
    if current.get("cash_conversion_state") == "PROFIT_POSITIVE_CASH_FLOW_NEGATIVE":
        risks.append("Pozitif dönem kârına rağmen işletme nakit akışı negatif.")
    if current.get("other_income_state") == "OTHER_OPERATING_INCOME_EXCEEDS_REVENUE":
        risks.append(
            "Diğer faaliyet gelirleri satış gelirini aşıyor; kârın bileşimi ayrıca incelenmeli."
        )
    if (
        current.get("operating_bridge_state")
        == "CORE_OPERATING_NEGATIVE_REPORTED_OPERATING_POSITIVE"
    ):
        risks.append(
            "Net faaliyet sonucu negatifken raporlanan faaliyet kârı pozitif; farkın kaynağı "
            "diğer faaliyet kalemlerinde."
        )

    revenue_growth = comparative.get("revenue_growth") if comparative.get("available") else None
    if isinstance(revenue_growth, Mapping) and revenue_growth.get("status") == "OK":
        growth = _finite(revenue_growth.get("value"))
        if growth is not None:
            if growth > 0:
                positives.append("Cari rapordaki satış geliri geçen yılın aynı döneminin üzerinde.")
            elif growth < 0:
                risks.append("Cari rapordaki satış geliri geçen yılın aynı döneminin altında.")

    if comparative.get("available"):
        caveats.append(
            "Karşılaştırma cari sağlayıcı tablosundaki karşılaştırmalı sütundan gelir; "
            "tarihsel point-in-time snapshot değildir."
        )
    if snapshot.inflation_accounting:
        caveats.append(
            "TMS29/enflasyon muhasebesi nedeniyle dönemler arası TTM köprüsü ayrıca ortak "
            "satın alma gücü baz tarihi doğrulanmadan kullanılmaz."
        )

    if risks and positives:
        state = "MIXED_BALANCE_STRONGER_THAN_EARNINGS_QUALITY"
        headline = "Bilanço kaldıraç tarafı görece rahat; kârın nakit ve gelir bileşimi daha zayıf."
    elif risks:
        state = "QUALITY_RISKS_DOMINATE"
        headline = "Cari finansallarda kâr kalitesi ve nakit dönüşümü açısından riskler öne çıkıyor."
    elif positives:
        state = "CURRENT_PERIOD_POSITIVE"
        headline = "Cari dönem finansalları bilanço ve faaliyet göstergelerinde olumlu unsurlar taşıyor."
    else:
        state = "INSUFFICIENT"
        headline = "Cari dönem temel görünümü için yeterli canonical finansal kalem yok."

    return {
        "state": state,
        "headline": headline,
        "positives": positives,
        "risks": risks,
        "caveats": caveats,
    }


def build_current_period_fundamental_view(
    snapshot: FinancialSnapshot,
    *,
    comparative: PeriodComparative | None = None,
) -> dict[str, Any]:
    """Build a current-report fundamental view without pretending TTM is valid.

    Especially for GYO/TMS29 cases, this layer gives safe balance-sheet and YTD
    diagnostics while the stricter point-in-time TTM engine can remain
    unavailable until purchasing-power bases and historical filings are proven.
    """
    balance = _balance_view(snapshot)
    current = _income_cash_view(snapshot)
    comparative_view = _comparative_view(snapshot, current, comparative)
    synthesis = _synthesis(snapshot, balance, current, comparative_view)

    return {
        "available": True,
        "symbol": snapshot.symbol.strip().upper(),
        "sector_type": snapshot.sector_type.value,
        "period_end": snapshot.period_end,
        "published_at": snapshot.published_at,
        "currency": snapshot.currency,
        "basis": "CURRENT_PUBLISHED_REPORT",
        "balance": balance,
        "current_period": current,
        "comparative": comparative_view,
        "synthesis": synthesis,
        "quality": {
            "point_in_time_current_snapshot": True,
            "comparative_point_in_time": False if comparative is not None else None,
            "gyo_specific_balance_view": snapshot.sector_type == SectorType.GYO,
            "no_fair_value_gain_inference": True,
            "no_auto_trade_decision": True,
        },
    }
