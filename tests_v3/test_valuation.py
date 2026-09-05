import unittest
from datetime import datetime, timezone

from market_core.fundamental_metrics import build_fundamental_metrics
from market_core.fundamental_models import FinancialSnapshot, SectorType, StatementType
from market_core.ttm import TTMResult
from market_core.valuation import NOT_MEANINGFUL, OK, UNAVAILABLE, build_daily_valuation


UTC = timezone.utc


class ValuationTests(unittest.TestCase):
    def _snapshot(
        self,
        *,
        sector: SectorType = SectorType.INDUSTRIAL,
        equity: float = 500.0,
        shares: float | None = 100.0,
        nav_value: float | None = None,
    ) -> FinancialSnapshot:
        metadata = {}
        if nav_value is not None:
            metadata["nav_value"] = nav_value
        return FinancialSnapshot(
            symbol="TEST",
            sector_type=sector,
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, tzinfo=UTC),
            currency="TRY",
            scale=1.0,
            statement_type=StatementType.QUARTERLY,
            inflation_accounting="TMS29",
            balance_sheet={
                "equity": equity,
                "total_assets": 1_000.0,
                "total_financial_debt": 200.0,
                "cash_and_equivalents": 50.0,
                "current_assets": 300.0,
                "current_liabilities": 150.0,
                "investment_property_fair_value": 800.0,
            },
            shares_outstanding=shares,
            metadata=metadata,
        )

    def _ttm(
        self,
        *,
        net_income: float = 100.0,
        revenue: float = 1_000.0,
        ebitda: float = 200.0,
        ocf: float = 140.0,
        capex: float = 40.0,
    ) -> TTMResult:
        return TTMResult(
            symbol="TEST",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            currency="TRY",
            available=True,
            method="TEST",
            income_statement={
                "revenue": revenue,
                "gross_profit": 400.0,
                "ebitda": ebitda,
                "ebit": 160.0,
                "net_income": net_income,
                "profit_before_tax": 125.0,
                "tax_expense": 25.0,
                "interest_expense": 20.0,
            },
            cash_flow={
                "operating_cash_flow": ocf,
                "capital_expenditures": capex,
            },
            quality={"point_in_time": True},
        )

    def test_price_changes_recalculate_multiples_with_same_snapshot(self) -> None:
        snapshot = self._snapshot()
        ttm = self._ttm()
        fundamentals = build_fundamental_metrics(snapshot, ttm)
        low = build_daily_valuation(
            snapshot,
            ttm,
            price=10.0,
            price_currency="TRY",
            fundamental_state=fundamentals,
        )
        high = build_daily_valuation(
            snapshot,
            ttm,
            price=20.0,
            price_currency="TRY",
            fundamental_state=fundamentals,
        )
        self.assertTrue(low.available)
        self.assertTrue(high.available)
        self.assertEqual(low.market_cap.value, 1_000.0)
        self.assertEqual(high.market_cap.value, 2_000.0)
        self.assertAlmostEqual(low.multiples["pe"].value or 0, 10.0)
        self.assertAlmostEqual(high.multiples["pe"].value or 0, 20.0)
        self.assertLess(low.multiples["ev_to_ebitda"].value or 0, high.multiples["ev_to_ebitda"].value or 0)

    def test_negative_earnings_makes_pe_not_meaningful(self) -> None:
        snapshot = self._snapshot()
        ttm = self._ttm(net_income=-10.0)
        state = build_daily_valuation(snapshot, ttm, price=10.0, price_currency="TRY")
        self.assertEqual(state.multiples["pe"].status, NOT_MEANINGFUL)
        self.assertIsNone(state.multiples["pe"].value)

    def test_negative_equity_makes_pb_not_meaningful(self) -> None:
        snapshot = self._snapshot(equity=-50.0)
        state = build_daily_valuation(snapshot, self._ttm(), price=10.0, price_currency="TRY")
        self.assertEqual(state.multiples["pb"].status, NOT_MEANINGFUL)

    def test_missing_shares_blocks_market_cap_family(self) -> None:
        snapshot = self._snapshot(shares=None)
        state = build_daily_valuation(snapshot, self._ttm(), price=10.0, price_currency="TRY")
        self.assertFalse(state.available)
        self.assertEqual(state.market_cap.status, UNAVAILABLE)
        self.assertIn("pay sayısı", (state.reason or "").lower())

    def test_currency_mismatch_blocks_valuation(self) -> None:
        state = build_daily_valuation(self._snapshot(), self._ttm(), price=10.0, price_currency="USD")
        self.assertFalse(state.available)
        self.assertIn("para birimleri", (state.reason or "").lower())

    def test_negative_free_cash_flow_yield_is_valid_not_cheap_signal(self) -> None:
        snapshot = self._snapshot()
        ttm = self._ttm(ocf=20.0, capex=40.0)
        state = build_daily_valuation(snapshot, ttm, price=10.0, price_currency="TRY")
        metric = state.multiples["fcf_yield"]
        self.assertEqual(metric.status, OK)
        self.assertAlmostEqual(metric.value or 0, -0.02)

    def test_gyo_nav_discount_requires_explicit_nav(self) -> None:
        no_nav = self._snapshot(sector=SectorType.GYO, nav_value=None)
        no_nav_state = build_daily_valuation(no_nav, self._ttm(), price=2.0, price_currency="TRY")
        self.assertEqual(no_nav_state.sector_metrics["nav_discount"].status, UNAVAILABLE)
        self.assertIn("özkaynak nav değildir", (no_nav_state.sector_metrics["nav_discount"].reason or "").lower())

        with_nav = self._snapshot(sector=SectorType.GYO, nav_value=400.0)
        with_nav_state = build_daily_valuation(with_nav, self._ttm(), price=2.0, price_currency="TRY")
        discount = with_nav_state.sector_metrics["nav_discount"]
        self.assertEqual(discount.status, OK)
        self.assertAlmostEqual(discount.value or 0, 0.5)
        self.assertAlmostEqual(with_nav_state.sector_metrics["price_to_nav"].value or 0, 0.5)


if __name__ == "__main__":
    unittest.main()
