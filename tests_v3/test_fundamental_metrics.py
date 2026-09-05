import unittest
from datetime import datetime, timezone

from market_core.fundamental_metrics import (
    NOT_MEANINGFUL,
    OK,
    UNAVAILABLE,
    build_fundamental_metrics,
)
from market_core.fundamental_models import FinancialSnapshot, SectorType, StatementType
from market_core.ttm import TTMResult


UTC = timezone.utc


class FundamentalMetricsTests(unittest.TestCase):
    def _snapshot(
        self,
        *,
        sector: SectorType = SectorType.INDUSTRIAL,
        period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC),
        equity: float = 120.0,
        assets: float = 300.0,
        debt: float = 80.0,
        cash: float = 20.0,
        current_assets: float = 100.0,
        current_liabilities: float = 60.0,
        portfolio_value: float | None = None,
        nav_value: float | None = None,
    ) -> FinancialSnapshot:
        balance = {
            "equity": equity,
            "total_assets": assets,
            "total_financial_debt": debt,
            "cash_and_equivalents": cash,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
        }
        if portfolio_value is not None:
            balance["investment_property_fair_value"] = portfolio_value
        metadata = {}
        if nav_value is not None:
            metadata["nav_value"] = nav_value
        return FinancialSnapshot(
            symbol="TEST",
            sector_type=sector,
            period_end=period_end,
            published_at=datetime(2026, 8, 10, tzinfo=UTC),
            currency="TRY",
            scale=1.0,
            statement_type=StatementType.QUARTERLY,
            inflation_accounting="TMS29",
            balance_sheet=balance,
            shares_outstanding=100.0,
            metadata=metadata,
        )

    def _ttm(
        self,
        *,
        revenue: float = 200.0,
        net_income: float = 30.0,
        currency: str = "TRY",
    ) -> TTMResult:
        return TTMResult(
            symbol="TEST",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            currency=currency,
            available=True,
            method="TEST",
            income_statement={
                "revenue": revenue,
                "gross_profit": 80.0,
                "ebitda": 50.0,
                "ebit": 40.0,
                "net_income": net_income,
                "profit_before_tax": 35.0,
                "tax_expense": 7.0,
                "interest_expense": 10.0,
                "rental_revenue": 90.0,
                "fair_value_gain_investment_property": 10.0,
            },
            cash_flow={
                "operating_cash_flow": 36.0,
                "capital_expenditures": 12.0,
            },
            quality={"point_in_time": True},
        )

    def test_generic_metrics_use_average_balances_and_cash_quality(self) -> None:
        current = self._snapshot()
        prior = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            equity=100.0,
            assets=250.0,
            debt=70.0,
            cash=10.0,
            current_assets=90.0,
            current_liabilities=55.0,
        )
        prior_ttm = self._ttm(revenue=160.0, net_income=20.0)
        state = build_fundamental_metrics(
            current,
            self._ttm(),
            prior_snapshot=prior,
            prior_ttm=prior_ttm,
        )
        metrics = state["metrics"]
        self.assertTrue(state["available"])
        self.assertAlmostEqual(metrics["revenue_growth"].value or 0, 0.25)
        self.assertAlmostEqual(metrics["gross_margin"].value or 0, 0.40)
        self.assertAlmostEqual(metrics["ebitda_margin"].value or 0, 0.25)
        self.assertAlmostEqual(metrics["net_margin"].value or 0, 0.15)
        self.assertAlmostEqual(metrics["roe"].value or 0, 30.0 / 110.0)
        self.assertAlmostEqual(metrics["roa"].value or 0, 30.0 / 275.0)
        self.assertAlmostEqual(metrics["net_debt"].value or 0, 60.0)
        self.assertAlmostEqual(metrics["net_debt_to_ebitda"].value or 0, 1.2)
        self.assertAlmostEqual(metrics["interest_coverage"].value or 0, 4.0)
        self.assertAlmostEqual(metrics["operating_cash_flow_to_net_income"].value or 0, 1.2)
        self.assertAlmostEqual(metrics["free_cash_flow"].value or 0, 24.0)
        self.assertAlmostEqual(metrics["working_capital_change"].value or 0, 5.0)
        self.assertAlmostEqual(metrics["roic"].value or 0, 32.0 / 170.0)
        self.assertEqual(metrics["roe"].basis, "AVERAGE_BALANCE")

    def test_roe_fails_closed_without_comparable_prior_balance(self) -> None:
        state = build_fundamental_metrics(self._snapshot(), self._ttm())
        self.assertEqual(state["metrics"]["roe"].status, UNAVAILABLE)
        self.assertEqual(state["metrics"]["roa"].status, UNAVAILABLE)

    def test_negative_net_income_makes_cash_conversion_not_meaningful(self) -> None:
        state = build_fundamental_metrics(self._snapshot(), self._ttm(net_income=-5.0))
        metric = state["metrics"]["operating_cash_flow_to_net_income"]
        self.assertEqual(metric.status, NOT_MEANINGFUL)
        self.assertIsNone(metric.value)

    def test_gyo_never_uses_equity_as_nav(self) -> None:
        current = self._snapshot(
            sector=SectorType.GYO,
            debt=120.0,
            cash=20.0,
            portfolio_value=500.0,
            nav_value=None,
        )
        state = build_fundamental_metrics(current, self._ttm())
        sector = state["sector_metrics"]
        self.assertEqual(sector["ltv"].status, OK)
        self.assertAlmostEqual(sector["ltv"].value or 0, 0.20)
        self.assertEqual(sector["reported_nav"].status, UNAVAILABLE)
        self.assertIsNone(sector["reported_nav"].value)
        self.assertIn("özkaynak", (sector["reported_nav"].reason or "").lower())
        self.assertAlmostEqual(sector["rental_revenue_share"].value or 0, 0.45)

    def test_explicit_gyo_nav_is_accepted_but_not_invented(self) -> None:
        current = self._snapshot(
            sector=SectorType.GYO,
            portfolio_value=500.0,
            nav_value=420.0,
        )
        state = build_fundamental_metrics(current, self._ttm())
        nav = state["sector_metrics"]["reported_nav"]
        self.assertEqual(nav.status, OK)
        self.assertEqual(nav.value, 420.0)
        self.assertEqual(nav.basis, "EXPLICIT_PROVIDER_NAV")

    def test_currency_mismatch_blocks_metric_family(self) -> None:
        state = build_fundamental_metrics(self._snapshot(), self._ttm(currency="USD"))
        self.assertFalse(state["available"])
        self.assertIn("para birimleri", state["reason"])


if __name__ == "__main__":
    unittest.main()
