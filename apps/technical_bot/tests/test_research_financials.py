from __future__ import annotations

from src.research_financials import _altman, _beneish, _piotroski


def test_altman_requires_complete_evidence() -> None:
    full = _altman(
        assets=1_000.0,
        liabilities=400.0,
        working_capital=180.0,
        retained_earnings=250.0,
        ebit=140.0,
        market_cap=1_600.0,
        revenue=1_200.0,
    )
    assert full["value"] is not None
    assert full["coverage"] == 1.0

    missing = _altman(
        assets=1_000.0,
        liabilities=400.0,
        working_capital=180.0,
        retained_earnings=None,
        ebit=140.0,
        market_cap=1_600.0,
        revenue=1_200.0,
    )
    assert missing["value"] is None
    assert missing["coverage"] < 1.0


def test_beneish_does_not_impute_missing_component_as_zero() -> None:
    full = _beneish(
        revenue=1_200.0,
        revenue_prev=1_000.0,
        receivables=180.0,
        receivables_prev=140.0,
        gross_profit=420.0,
        gross_profit_prev=360.0,
        current_assets=550.0,
        current_assets_prev=500.0,
        ppe=380.0,
        ppe_prev=360.0,
        assets=1_300.0,
        assets_prev=1_180.0,
        depreciation=45.0,
        depreciation_prev=42.0,
        sga=130.0,
        sga_prev=118.0,
        liabilities=520.0,
        liabilities_prev=500.0,
        net_income=120.0,
        cfo=135.0,
    )
    assert full["value"] is not None
    assert full["coverage"] == 1.0
    assert len(full["components"]) == 8

    partial = _beneish(
        revenue=1_200.0,
        revenue_prev=1_000.0,
        receivables=180.0,
        receivables_prev=140.0,
        gross_profit=420.0,
        gross_profit_prev=360.0,
        current_assets=550.0,
        current_assets_prev=500.0,
        ppe=380.0,
        ppe_prev=360.0,
        assets=1_300.0,
        assets_prev=1_180.0,
        depreciation=None,
        depreciation_prev=42.0,
        sga=130.0,
        sga_prev=118.0,
        liabilities=520.0,
        liabilities_prev=500.0,
        net_income=120.0,
        cfo=135.0,
    )
    assert partial["value"] is None
    assert partial["coverage"] < 1.0


def test_piotroski_reports_observed_denominator_when_evidence_missing() -> None:
    score = _piotroski(
        roa=8.0,
        roa_prev=6.0,
        cfo=150.0,
        net_income=120.0,
        leverage=0.20,
        leverage_prev=0.25,
        current_ratio=1.8,
        current_ratio_prev=1.5,
        paid_capital=None,
        paid_capital_prev=None,
        gross_margin=32.0,
        gross_margin_prev=30.0,
        asset_turnover=1.25,
        asset_turnover_prev=1.10,
    )
    assert score["score"] == 8
    assert score["max_score"] == 8
    assert score["official_score"] is None
    assert score["coverage"] == 0.89
    assert score["criteria"]["no_dilution_proxy"] is None
