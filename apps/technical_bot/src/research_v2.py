"""Production research v2 with statement-derived financial and peer intelligence."""

from __future__ import annotations

from dataclasses import replace

from src import research_engine as core
from src import research_risk as audited
from src.research_financials import enrich_financial_analysis, enrich_valuation

VALUATION_MULTIPLES = ("pe", "pb", "ev_ebitda", "ev_sales", "ps", "p_fcf", "peg")
GYO_NON_COMPARABLE_MARGIN_LIMIT = 500.0


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


def _positive_multiple(value):
    number = core._finite(value)
    if number is None or number <= 0 or number >= 10_000:
        return None
    return number


def _sanitize_valuation(valuation: dict) -> dict:
    """Remove provider sentinels and keep yield/multiple definitions internally coherent."""
    result = dict(valuation)
    metrics = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in valuation.get("metrics", {}).items()
    }
    for key in VALUATION_MULTIPLES:
        item = metrics.get(key)
        if not isinstance(item, dict):
            continue
        item["value"] = _positive_multiple(item.get("value"))
        metrics[key] = item

    pe_item = metrics.get("pe")
    pe = _positive_multiple(pe_item.get("value")) if isinstance(pe_item, dict) else None
    if pe is not None:
        earnings = dict(metrics.get("earnings_yield") or {})
        earnings["value"] = 100.0 / pe
        earnings.setdefault("percentile", None)
        metrics["earnings_yield"] = earnings

    p_fcf_item = metrics.get("p_fcf")
    p_fcf = _positive_multiple(p_fcf_item.get("value")) if isinstance(p_fcf_item, dict) else None
    if p_fcf is not None:
        fcf_yield = dict(metrics.get("fcf_yield") or {})
        fcf_yield["value"] = 100.0 / p_fcf
        fcf_yield.setdefault("percentile", None)
        metrics["fcf_yield"] = fcf_yield

    peer = dict(valuation.get("peer_analysis", {}))
    clean_peers = []
    for raw_peer in peer.get("peers", ()):
        item = dict(raw_peer)
        for key in ("pe", "pb", "ev_ebitda", "ev_sales"):
            item[key] = _positive_multiple(item.get(key))
        clean_peers.append(item)
    peer["peers"] = clean_peers

    result["metrics"] = metrics
    result["peer_analysis"] = peer
    result["multiple_quality_note"] = (
        "Negatif/anlamsız sağlayıcı sentinel çarpanları N/M kabul edilir. Kazanç verimi geçerli F/K'nın, "
        "FCF verimi geçerli Fiyat/FCF'nin tersidir; böylece aynı kartta çelişkili tanım kullanılmaz."
    )
    return result


def _sanitize_profile_financials(financial: dict, profile: str) -> dict:
    """Keep economically non-comparable ratios out of the scorecard without deleting raw evidence."""
    if profile != "GYO":
        return financial

    result = dict(financial)
    metrics = dict(financial.get("metrics", {}))
    raw_non_comparable: dict[str, float] = {}
    for key in (
        "operating_margin",
        "operating_margin_quarterly",
        "net_margin",
        "net_margin_quarterly",
    ):
        value = core._finite(metrics.get(key))
        if value is not None and abs(value) > GYO_NON_COMPARABLE_MARGIN_LIMIT:
            raw_non_comparable[key] = value
            metrics[key] = None

    if raw_non_comparable:
        result["non_comparable_metrics"] = raw_non_comparable
        result["ratio_note"] = (
            str(result.get("ratio_note", ""))
            + " GYO'da yatırım amaçlı gayrimenkul değerleme/tek seferlik faaliyet kalemleri nedeniyle "
            "ekonomik olarak karşılaştırılamayan aşırı marjlar kartta N/M bırakılır; ham değer JSON'da korunur."
        ).strip()
    result["metrics"] = metrics

    ratio_groups = []
    for group in result.get("ratio_groups", ()):
        group_copy = dict(group)
        rows = []
        for row in group.get("rows", ()):
            row_copy = dict(row)
            row_copy["value"] = metrics.get(row_copy.get("key"))
            rows.append(row_copy)
        group_copy["rows"] = tuple(rows)
        ratio_groups.append(group_copy)
    result["ratio_groups"] = tuple(ratio_groups)
    return result


def _sync_financial_labels(report):
    """Expose the same coverage-gated conclusion everywhere in cards and commentary."""
    financial = dict(report.financial)
    by_name = {item.name: item for item in report.dimensions}
    balance = by_name.get("Bilanço Trendi")
    earnings = by_name.get("Kâr Kalitesi")
    if balance is not None:
        financial["balance_label"] = balance.label
        financial["balance_score"] = balance.score
        financial["balance_coverage"] = balance.coverage
    if earnings is not None:
        financial["earnings_quality_label"] = earnings.label
        financial["earnings_quality_score"] = earnings.score
        financial["earnings_quality_coverage"] = earnings.coverage
    return replace(report, financial=financial)


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
    financial = _sanitize_profile_financials(financial, report.profile)
    valuation = enrich_valuation(
        report.valuation,
        financial,
        symbol=report.symbol,
        profile=report.profile,
    )
    valuation = _sanitize_valuation(valuation)
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
    report = audited._finalize_dimensions(report)
    return _sync_financial_labels(report)
