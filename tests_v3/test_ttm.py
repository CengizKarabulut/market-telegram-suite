import unittest
from datetime import datetime, timezone

from market_core.fundamental_models import FinancialSnapshot, SectorType, StatementType
from market_core.ttm import assemble_ttm


UTC = timezone.utc


class TTMTests(unittest.TestCase):
    def _snapshot(
        self,
        *,
        period_end: datetime,
        published_at: datetime,
        statement_type: StatementType,
        revenue: float,
        net_income: float,
        ocf: float,
        capex: float,
        flow_basis: str | None = None,
        scale: float = 1.0,
        inflation_accounting: str | None = None,
        price_level_date: str | None = None,
        restatement_id: str | None = None,
    ) -> FinancialSnapshot:
        metadata = {}
        if flow_basis is not None:
            metadata["flow_basis"] = flow_basis
        if price_level_date is not None:
            metadata["price_level_date"] = price_level_date
        return FinancialSnapshot(
            symbol="ZGYO",
            sector_type=SectorType.GYO,
            period_end=period_end,
            published_at=published_at,
            currency="TRY",
            scale=scale,
            statement_type=statement_type,
            inflation_accounting=inflation_accounting,
            restatement_id=restatement_id,
            income_statement={"revenue": revenue, "net_income": net_income},
            cash_flow={"operating_cash_flow": ocf, "capital_expenditures": capex},
            balance_sheet={"equity": 100.0},
            shares_outstanding=84_480_000.0,
            metadata=metadata,
        )

    def test_annual_snapshot_is_direct_ttm_and_scale_is_normalized(self) -> None:
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 2, 20, 18, 0, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
            scale=1_000.0,
            inflation_accounting="TMS29",
        )
        result = assemble_ttm(
            [annual],
            symbol="ZGYO",
            as_of=datetime(2026, 2, 21, tzinfo=UTC),
        )
        self.assertTrue(result.available)
        self.assertEqual(result.method, "ANNUAL_DIRECT")
        self.assertEqual(result.income_statement["revenue"], 100_000.0)
        self.assertEqual(result.cash_flow["operating_cash_flow"], 18_000.0)

    def test_cumulative_ytd_uses_annual_plus_current_minus_prior(self) -> None:
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2025, 8, 10, 18, 0, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=45.0,
            net_income=8.0,
            ocf=7.0,
            capex=2.0,
            flow_basis="CUMULATIVE_YTD",
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 2, 20, 18, 0, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
        )
        current_ytd = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 24, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=70.0,
            net_income=15.0,
            ocf=13.0,
            capex=4.0,
            flow_basis="CUMULATIVE_YTD",
        )
        result = assemble_ttm(
            [prior_ytd, annual, current_ytd],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertTrue(result.available)
        self.assertEqual(result.method, "ANNUAL_PLUS_CURRENT_YTD_MINUS_PRIOR_YTD")
        self.assertAlmostEqual(result.income_statement["revenue"], 125.0)
        self.assertAlmostEqual(result.income_statement["net_income"], 27.0)
        self.assertAlmostEqual(result.cash_flow["operating_cash_flow"], 24.0)
        self.assertAlmostEqual(result.cash_flow["capital_expenditures"], 7.0)

    def test_future_restatement_does_not_leak_into_ttm(self) -> None:
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2025, 8, 10, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=40.0,
            net_income=6.0,
            ocf=5.0,
            capex=1.0,
            flow_basis="CUMULATIVE_YTD",
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 2, 20, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
        )
        current_original = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            restatement_id="original",
        )
        current_restated = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 25, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=90.0,
            net_income=30.0,
            ocf=22.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            restatement_id="restated",
        )
        result = assemble_ttm(
            [prior_ytd, annual, current_original, current_restated],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 20, tzinfo=UTC),
        )
        self.assertTrue(result.available)
        self.assertEqual(result.income_statement["revenue"], 120.0)
        current_component = next(item for item in result.components if item["role"] == "CURRENT_YTD")
        self.assertEqual(current_component["restatement_id"], "original")

    def test_interim_flow_basis_must_be_explicit(self) -> None:
        current = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis=None,
        )
        result = assemble_ttm(
            [current],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertFalse(result.available)
        self.assertIn("CUMULATIVE_YTD", result.reason or "")

    def test_incompatible_inflation_accounting_blocks_ttm(self) -> None:
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2025, 8, 10, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=40.0,
            net_income=6.0,
            ocf=5.0,
            capex=1.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 2, 20, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
            inflation_accounting="TMS29",
        )
        current = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="NO_TMS29",
        )
        result = assemble_ttm(
            [prior_ytd, annual, current],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertFalse(result.available)
        self.assertIn("enflasyon muhasebesi", (result.reason or "").lower())

    def test_tms29_interim_requires_explicit_price_level_date(self) -> None:
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=40.0,
            net_income=6.0,
            ocf=5.0,
            capex=1.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 3, 2, 22, 44, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
            inflation_accounting="TMS29",
        )
        current = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
        )
        result = assemble_ttm(
            [prior_ytd, annual, current],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertFalse(result.available)
        self.assertIn("price_level_date", result.reason or "")

    def test_tms29_interim_requires_matching_price_level_dates(self) -> None:
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=40.0,
            net_income=6.0,
            ocf=5.0,
            capex=1.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
            price_level_date="2026-06-30",
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 3, 2, 22, 44, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
            inflation_accounting="TMS29",
            price_level_date="2025-12-31",
        )
        current = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
            price_level_date="2026-06-30",
        )
        result = assemble_ttm(
            [prior_ytd, annual, current],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertFalse(result.available)
        self.assertIn("baz tarih", (result.reason or "").lower())

    def test_tms29_interim_succeeds_with_common_price_level_date(self) -> None:
        common_basis = "2026-06-30"
        prior_ytd = self._snapshot(
            period_end=datetime(2025, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=40.0,
            net_income=6.0,
            ocf=5.0,
            capex=1.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
            price_level_date=common_basis,
        )
        annual = self._snapshot(
            period_end=datetime(2025, 12, 31, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.ANNUAL,
            revenue=100.0,
            net_income=20.0,
            ocf=18.0,
            capex=5.0,
            inflation_accounting="TMS29",
            price_level_date=common_basis,
        )
        current = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 32, tzinfo=UTC),
            statement_type=StatementType.QUARTERLY,
            revenue=60.0,
            net_income=12.0,
            ocf=10.0,
            capex=3.0,
            flow_basis="CUMULATIVE_YTD",
            inflation_accounting="TMS29",
            price_level_date=common_basis,
        )
        result = assemble_ttm(
            [prior_ytd, annual, current],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 11, tzinfo=UTC),
        )
        self.assertTrue(result.available)
        self.assertEqual(result.quality["price_level_date"], common_basis)
        for component in result.components:
            self.assertEqual(component["price_level_date"], common_basis)


if __name__ == "__main__":
    unittest.main()
