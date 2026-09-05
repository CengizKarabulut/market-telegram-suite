"""Auditable risk layer for the integrated research command.

Bank capital strength is a higher-is-better proxy. Official SYR/NPL values are
never inferred when the provider does not expose them.
"""

from __future__ import annotations

from src import research_engine as core
from src.research_engine import LevelZone, RiskItem


def _risk_engine(
    profile: str,
    financial: dict,
    valuation: dict,
    technical: dict,
    supports: tuple[LevelZone, ...],
) -> tuple[RiskItem | None, tuple[RiskItem, ...]]:
    fm = financial.get("metrics", {})
    risks: list[RiskItem] = []

    if profile == "BANK":
        capital_proxy = fm.get("equity_assets")
        loan_deposit = fm.get("loans_deposits")
        bank_score, _ = core._weighted(
            [
                (core._score_higher(capital_proxy, 5.0, 14.0), 1.0),
                (
                    core._score_lower(
                        abs((loan_deposit or 0.9) - 0.9),
                        0.0,
                        0.5,
                    ),
                    1.0,
                ),
            ]
        )
        bank_risk = 50.0 if bank_score is None else 100.0 - bank_score
        risks.append(
            RiskItem(
                "Banka bilanço riski",
                round(bank_risk, 1),
                "Resmi SYR/NPL yoksa özkaynak/aktif ve kredi/mevduat yalnız vekil göstergedir.",
            )
        )
    else:
        nde = fm.get("net_debt_equity")
        nd_ebitda = fm.get("net_debt_ebitda")
        current_ratio = fm.get("current_ratio")
        leverage_score, _ = core._weighted(
            [
                (core._score_lower(nde, 0.0, 2.0), 1.0),
                (core._score_lower(nd_ebitda, 0.0, 4.0), 1.2),
                (core._score_target(current_ratio, 1.2, 2.8, 0.5, 6.0), 0.8),
            ]
        )
        leverage_risk = 50.0 if leverage_score is None else 100.0 - leverage_score
        risks.append(
            RiskItem(
                "Finansal kaldıraç",
                round(leverage_risk, 1),
                f"Net borç yönü: {financial.get('debt_direction', '—')}; net borç/FAVÖK {nd_ebitda if nd_ebitda is not None else '—'}.",
            )
        )

    quality_score = financial.get("earnings_quality_score")
    if profile == "BANK":
        quality_evidence = (
            f"Net faiz büyümesi {fm.get('net_interest_growth', '—')} · "
            f"ROE {fm.get('roe', '—')} · gider büyümesi {fm.get('operating_expense_growth', '—')}."
        )
    else:
        quality_evidence = (
            f"CFO/net kâr {fm.get('cfo_net_income', '—')} · accrual %{fm.get('accrual_ratio', '—')}."
        )
    risks.append(
        RiskItem(
            "Kâr kalitesi",
            round(50.0 if quality_score is None else 100.0 - float(quality_score), 1),
            quality_evidence,
        )
    )

    valuation_score = valuation.get("score")
    risks.append(
        RiskItem(
            "Değerleme hassasiyeti",
            round(50.0 if valuation_score is None else 100.0 - float(valuation_score), 1),
            f"Karşılaştırma kapsamı: {valuation.get('scope', '—')}.",
        )
    )

    technical_score = technical.get("score")
    atr_pct = core._finite(technical.get("atr_pct"))
    support_penalty = 15.0 if not supports else min(float(supports[0].distance_atr) * 4.0, 20.0)
    technical_risk = 50.0 if technical_score is None else 100.0 - float(technical_score)
    technical_risk = min(
        100.0,
        technical_risk + support_penalty + (10.0 if atr_pct is not None and atr_pct > 5 else 0.0),
    )
    risks.append(
        RiskItem(
            "Teknik yapı",
            round(technical_risk, 1),
            (
                f"Yapı {technical.get('structure', {}).get('state', '—')} · ATR %{atr_pct:.1f}"
                if atr_pct is not None
                else "Teknik volatilite verisi yetersiz."
            ),
        )
    )

    turnover = core._finite(technical.get("average_turnover_20"))
    if turnover is None:
        liquidity_risk = 50.0
    elif turnover < 25_000_000:
        liquidity_risk = 85.0
    elif turnover < 100_000_000:
        liquidity_risk = 55.0
    else:
        liquidity_risk = 20.0
    risks.append(
        RiskItem(
            "Likidite",
            liquidity_risk,
            f"20 günlük ortalama TL hacim {turnover:,.0f}." if turnover else "TL hacim hesaplanamadı.",
        )
    )

    ordered = tuple(sorted(risks, key=lambda item: item.score, reverse=True))
    return (ordered[0] if ordered else None), ordered


def build_research_report(symbol: str):
    """Build through the core engine with the corrected risk layer."""
    previous = core._risk_engine
    core._risk_engine = _risk_engine
    try:
        return core.build_research_report(symbol)
    finally:
        core._risk_engine = previous
