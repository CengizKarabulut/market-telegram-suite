import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from market_core.fundamental_models import SectorType
from market_core.fundamental_sources.borsapy_adapter import (
    CanonicalRowMap,
    RowSelector,
    build_snapshot_from_borsapy_tables,
)
from market_core.fundamental_sources.kap_metadata import KapFilingMetadata


ISTANBUL = ZoneInfo("Europe/Istanbul")


class BorsaPyAdapterTests(unittest.TestCase):
    def _filing(self) -> KapFilingMetadata:
        return KapFilingMetadata(
            disclosure_id=1647006,
            title="Finansal Rapor",
            published_at=datetime(2026, 8, 10, 18, 32, 46, tzinfo=ISTANBUL),
            disclosure_type="FR",
            report_year=2026,
            period_label="6 Aylık",
            period_end=datetime(2026, 6, 30, tzinfo=ISTANBUL),
            currency="TRY",
            consolidation="Konsolide Olmayan",
            url="https://www.kap.org.tr/tr/Bildirim/1647006",
            quality={"period_end_source": "KAP_CURRENT_PERIOD"},
        )

    def _duplicate_debt_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "2026Q2": [82.0, 82.0, 85.0, 85.0],
                "2026Q1": [81.0, 81.0, 92.0, 92.0],
            },
            index=[
                "Finansal Borçlar",
                "Finansal Borçlar",
                "Finansal Borçlar",
                "Finansal Borçlar",
            ],
        )

    def _snapshot(self, balance: pd.DataFrame, row_map: CanonicalRowMap):
        empty = pd.DataFrame({"2026Q2": []})
        return build_snapshot_from_borsapy_tables(
            symbol="ZGYO",
            sector_type=SectorType.GYO,
            filing=self._filing(),
            balance_sheet=balance,
            income_statement=empty,
            cash_flow=empty,
            row_map=row_map,
            value_scale=1.0,
            shares_outstanding=None,
            financial_group="XI_29",
            inflation_accounting="TMS29",
            flow_basis="CUMULATIVE_YTD",
        )

    def test_occurrence_is_evaluated_after_batch_duplicates_collapse(self) -> None:
        row_map = CanonicalRowMap(
            balance_sheet={
                "short_term_financial_debt": RowSelector(
                    aliases=("Finansal Borçlar",), occurrence=0
                ),
                "long_term_financial_debt": RowSelector(
                    aliases=("Finansal Borçlar",), occurrence=1
                ),
            }
        )
        snapshot = self._snapshot(self._duplicate_debt_frame(), row_map)
        self.assertEqual(snapshot.balance_sheet["short_term_financial_debt"], 82.0)
        self.assertEqual(snapshot.balance_sheet["long_term_financial_debt"], 85.0)

    def test_sum_distinct_rows_does_not_double_count_provider_batches(self) -> None:
        row_map = CanonicalRowMap(
            balance_sheet={
                "total_financial_debt": RowSelector(
                    aliases=("Finansal Borçlar",), aggregate="SUM_DISTINCT_ROWS"
                )
            }
        )
        snapshot = self._snapshot(self._duplicate_debt_frame(), row_map)
        self.assertEqual(snapshot.balance_sheet["total_financial_debt"], 167.0)
        match = snapshot.metadata["row_matches"]["balance_sheet"]["total_financial_debt"]
        self.assertEqual(match["positions"], [0, 2])
        self.assertEqual(match["provider_batch_duplicates_collapsed"], 2)

    def test_plain_alias_fails_closed_when_label_has_multiple_distinct_rows(self) -> None:
        row_map = CanonicalRowMap(
            balance_sheet={"total_financial_debt": ("Finansal Borçlar",)}
        )
        snapshot = self._snapshot(self._duplicate_debt_frame(), row_map)
        self.assertIsNone(snapshot.balance_sheet["total_financial_debt"])
        ambiguity = snapshot.metadata["ambiguous_canonical_rows"]["balance_sheet"]
        self.assertEqual(
            ambiguity["total_financial_debt"]["reason"],
            "MULTIPLE_DISTINCT_PROVIDER_ROWS",
        )

    def test_multiplier_is_explicit_for_provider_sign_normalization(self) -> None:
        cash_flow = pd.DataFrame(
            {"2026Q2": [-25.0], "2026Q1": [-10.0]},
            index=["Yatırım Harcamaları"],
        )
        balance = pd.DataFrame({"2026Q2": []})
        row_map = CanonicalRowMap(
            cash_flow={
                "capital_expenditures": RowSelector(
                    aliases=("Yatırım Harcamaları",), multiplier=-1.0
                )
            }
        )
        snapshot = build_snapshot_from_borsapy_tables(
            symbol="ZGYO",
            sector_type=SectorType.GYO,
            filing=self._filing(),
            balance_sheet=balance,
            income_statement=balance,
            cash_flow=cash_flow,
            row_map=row_map,
            value_scale=1.0,
            shares_outstanding=None,
            financial_group="XI_29",
            inflation_accounting="TMS29",
            flow_basis="CUMULATIVE_YTD",
        )
        self.assertEqual(snapshot.cash_flow["capital_expenditures"], 25.0)


if __name__ == "__main__":
    unittest.main()
