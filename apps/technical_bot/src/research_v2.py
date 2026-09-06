"""Production research v2 with statement-derived financial and peer intelligence."""

from __future__ import annotations

from dataclasses import replace

from src import research_engine as core
from src import research_risk as audited
from src.research_financials import enrich_financial_analysis, enrich_valuation


def _refresh_valuation_dimension(report):
    dimensions = []
    for item in report.dimensions:
        if item.name != "Değerleme":
            dimensions.append(item)
            continue
        score = report.valuation.get("score")
        coverage = report.valuation.get("coverage", 0.0)
        peer = report.valuation.get("peer_analysis", {})
        scope = peer.get("scope") or report.valuation.get("scope", "Karşılaştırma yok")
        dimensions.append(
            replace(
                item,
                score=score,
                coverage=coverage,
                label=core._label(score, "İSKONTOLU / GÜÇLÜ", "MAKUL", "PRİMLİ / ZAYIF"),
                summary=(
                    f"{scope} içinde göreli çarpanlar; PEG ve bilanço-türevi çarpanlar "
                    "ayrıca gösterilir."
                ),
            )
        )
    return replace(report, dimensions=tuple(dimensions))


def build_research_report(symbol: str):
    """Build audited research, then enrich it without weakening coverage gates."""
    report = audited.build_research_report(symbol)
    balance, income, cashflow = core._fetch_statements(report.symbol, report.profile)
    financial = enrich_financial_analysis(
        report.financial,
        report.fundamental,
        balance,
        income,
        cashflow,
    )
    valuation = enrich_valuation(
        report.valuation,
        financial,
        symbol=report.symbol,
        profile=report.profile,
    )
    report = replace(report, financial=financial, valuation=valuation)
    report = _refresh_valuation_dimension(report)

    main_risk, risks = audited._risk_engine(
        report.profile,
        report.financial,
        report.valuation,
        report.technical,
        report.supports,
    )
    report = replace(report, main_risk=main_risk, risks=risks)
    return audited._finalize_dimensions(report)
