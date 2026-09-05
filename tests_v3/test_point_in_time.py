import unittest
from datetime import datetime, timezone

from market_core.fundamental_models import FinancialSnapshot, SectorType, StatementType
from market_core.point_in_time import select_financial_snapshot


UTC = timezone.utc


class PointInTimeTests(unittest.TestCase):
    def _snapshot(
        self,
        *,
        period_end: datetime,
        published_at: datetime,
        restatement_id: str | None = None,
    ) -> FinancialSnapshot:
        return FinancialSnapshot(
            symbol="ZGYO",
            sector_type=SectorType.GYO,
            period_end=period_end,
            published_at=published_at,
            currency="TRY",
            scale=1.0,
            statement_type=StatementType.QUARTERLY,
            restatement_id=restatement_id,
            balance_sheet={"equity": 100.0},
            shares_outstanding=84_480_000.0,
        )

    def test_period_end_does_not_make_future_filing_visible(self) -> None:
        filing = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 24, tzinfo=UTC),
        )
        result = select_financial_snapshot(
            [filing],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 10, 18, 23, tzinfo=UTC),
        )
        self.assertIsNone(result.snapshot)
        self.assertEqual(result.excluded_future_count, 1)

    def test_filing_becomes_available_at_publication_timestamp(self) -> None:
        filing = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 24, tzinfo=UTC),
        )
        result = select_financial_snapshot(
            [filing],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 10, 18, 24, tzinfo=UTC),
        )
        self.assertEqual(result.snapshot, filing)

    def test_later_restatement_does_not_leak_into_earlier_as_of(self) -> None:
        original = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 10, 18, 24, tzinfo=UTC),
            restatement_id="original",
        )
        restated = self._snapshot(
            period_end=datetime(2026, 6, 30, tzinfo=UTC),
            published_at=datetime(2026, 8, 25, 9, 0, tzinfo=UTC),
            restatement_id="restated",
        )
        result = select_financial_snapshot(
            [original, restated],
            symbol="ZGYO",
            as_of=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
        )
        self.assertEqual(result.snapshot, original)
        self.assertEqual(result.excluded_future_count, 1)

    def test_naive_as_of_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_financial_snapshot([], symbol="ZGYO", as_of=datetime(2026, 8, 10))


if __name__ == "__main__":
    unittest.main()
