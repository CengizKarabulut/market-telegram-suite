import unittest
from datetime import datetime, timezone

from market_core.fundamental_models import FinancialSnapshot, SectorType, StatementType
from market_core.fundamental_period import (
    PeriodComparative,
    build_current_period_fundamental_view,
)


UTC = timezone.utc


class FundamentalPeriodViewTests(unittest.TestCase):
    def _snapshot(self) -> FinancialSnapshot:
        return FinancialSnapshot(
            symbol="ZGYO",
            sector_type=SectorType.GYO,
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 15, 32, 46, tzinfo=UTC),
            currency="TRY",
            scale=1.0,
            statement_type=StatementType.QUARTERLY,
            inflation_accounting="TMS29",
            balance_sheet={
                "cash_and_equivalents": 19_085_804.0,
                "current_assets": 427_568_666.0,
                "current_liabilities": 219_377_185.0,
                "equity": 4_069_164_476.0,
                "investment_property_fair_value": 5_373_169_206.0,
                "short_term_financial_debt": 82_675_100.0,
                "long_term_financial_debt": 85_160_778.0,
                "total_financial_debt": 167_835_878.0,
            },
            income_statement={
                "revenue": 6_827_976.0,
                "other_operating_income": 1_830_171_762.0,
                "ebit": 1_808_696_231.0,
                "net_income": 1_246_532_034.0,
            },
            cash_flow={"operating_cash_flow": -310_141_642.0},
            metadata={"flow_basis": "CUMULATIVE_YTD"},
        )

    def _comparative(self) -> PeriodComparative:
        return PeriodComparative(
            label="2025Q2",
            currency="TRY",
            scale=1.0,
            basis="CURRENT_PROVIDER_COMPARATIVE",
            income_statement={
                "revenue": 6_242_159.0,
                "net_income": 1_128_080_749.0,
            },
            cash_flow={"operating_cash_flow": 50_000_000.0},
        )

    def test_gyo_current_view_separates_low_leverage_from_cash_quality(self) -> None:
        result = build_current_period_fundamental_view(
            self._snapshot(),
            comparative=self._comparative(),
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["balance"]["leverage_state"], "LOW")
        self.assertAlmostEqual(result["balance"]["net_debt"], 148_750_074.0)
        self.assertAlmostEqual(result["balance"]["ltv"], 148_750_074.0 / 5_373_169_206.0)
        self.assertEqual(
            result["current_period"]["cash_conversion_state"],
            "PROFIT_POSITIVE_CASH_FLOW_NEGATIVE",
        )
        self.assertEqual(
            result["current_period"]["other_income_state"],
            "OTHER_OPERATING_INCOME_EXCEEDS_REVENUE",
        )
        self.assertEqual(
            result["synthesis"]["state"],
            "MIXED_BALANCE_STRONGER_THAN_EARNINGS_QUALITY",
        )

    def test_current_provider_comparative_is_not_labeled_point_in_time(self) -> None:
        result = build_current_period_fundamental_view(
            self._snapshot(),
            comparative=self._comparative(),
        )
        comparison = result["comparative"]
        self.assertTrue(comparison["available"])
        self.assertFalse(comparison["historical_point_in_time"])
        self.assertEqual(comparison["basis"], "CURRENT_PROVIDER_COMPARATIVE")
        self.assertGreater(comparison["revenue_growth"]["value"], 0.0)
        self.assertGreater(comparison["net_income_growth"]["value"], 0.0)

    def test_view_does_not_infer_fair_value_gain_from_other_operating_income(self) -> None:
        result = build_current_period_fundamental_view(self._snapshot())
        self.assertTrue(result["quality"]["no_fair_value_gain_inference"])
        self.assertNotIn("fair_value_gain", result["current_period"])
        self.assertIn("other_operating_income", result["current_period"])

    def test_growth_with_nonpositive_prior_is_not_meaningful(self) -> None:
        comparative = PeriodComparative(
            label="2025Q2",
            currency="TRY",
            scale=1.0,
            basis="CURRENT_PROVIDER_COMPARATIVE",
            income_statement={"revenue": 0.0, "net_income": -5.0},
        )
        result = build_current_period_fundamental_view(
            self._snapshot(),
            comparative=comparative,
        )
        self.assertEqual(
            result["comparative"]["revenue_growth"]["status"],
            "NOT_MEANINGFUL",
        )
        self.assertEqual(
            result["comparative"]["net_income_growth"]["status"],
            "NOT_MEANINGFUL",
        )


if __name__ == "__main__":
    unittest.main()
