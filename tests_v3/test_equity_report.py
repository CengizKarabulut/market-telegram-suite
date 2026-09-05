import unittest

from market_core.equity_report import (
    build_equity_report_contract,
    format_equity_report_preview,
)


class EquityReportTests(unittest.TestCase):
    def test_bearish_technical_and_positive_fundamental_is_explicit_conflict(self):
        report = build_equity_report_contract(
            symbol="ASELS",
            technical_report={"technical_synthesis": {"state": "BEARISH_ALIGNMENT"}},
            current_fundamental_view={
                "available": True,
                "synthesis": {"state": "CURRENT_PERIOD_POSITIVE"},
            },
        )
        synthesis = report["integrated_synthesis"]
        self.assertEqual(synthesis["state"], "CROSS_AXIS_CONFLICT")
        self.assertTrue(synthesis["conflicts"])
        self.assertFalse(synthesis["decision_contract"]["auto_buy_sell"])

    def test_peer_highlights_keep_mean_median_scope_basis_and_gap(self):
        report = build_equity_report_contract(
            symbol="THYAO",
            peer_benchmark={
                "available": True,
                "synthesis": {"state": "RELATIVELY_FAVOURABLE"},
                "metrics": {
                    "roe": {
                        "available": True,
                        "target_value": 0.22,
                        "peer_median": 0.15,
                        "peer_mean": 0.16,
                        "peer_q1": 0.10,
                        "peer_q3": 0.19,
                        "delta_to_median": 0.07,
                        "delta_to_mean": 0.06,
                        "percentile_rank": 0.85,
                        "position": "TOP_QUARTILE",
                        "favourability": "FAVOURABLE",
                        "scope": "PROVIDER_SECTOR_FALLBACK",
                        "benchmark_group": "PROVIDER_SECTOR::transportation",
                        "benchmark_label": "Transportation",
                        "basis": "TRADINGVIEW_TTM",
                    }
                },
            },
        )
        highlight = report["sector_and_peers"]["highlights"][0]
        self.assertEqual(highlight["peer_median"], 0.15)
        self.assertEqual(highlight["peer_mean"], 0.16)
        self.assertEqual(highlight["delta_to_median"], 0.07)
        self.assertEqual(highlight["scope"], "PROVIDER_SECTOR_FALLBACK")
        self.assertEqual(highlight["benchmark_label"], "Transportation")
        self.assertEqual(highlight["basis"], "TRADINGVIEW_TTM")
        self.assertEqual(highlight["metric_label"], "Özkaynak kârlılığı")

    def test_contextual_valuation_is_not_promoted_to_positive_signal(self):
        report = build_equity_report_contract(
            symbol="ZGYO",
            valuation_state={"available": True, "multiples": {"pb": 0.55}},
            peer_benchmark={
                "available": True,
                "synthesis": {"state": "NEUTRAL_OR_CONTEXTUAL"},
                "metrics": {
                    "price_to_book": {
                        "available": True,
                        "target_value": 0.55,
                        "peer_median": 0.80,
                        "peer_mean": 0.85,
                        "position": "BOTTOM_QUARTILE",
                        "favourability": "CONTEXTUAL",
                        "scope": "INDUSTRY_PEER_GROUP",
                    }
                },
            },
        )
        synthesis = report["integrated_synthesis"]
        self.assertFalse(any("ucuz" in item.casefold() for item in synthesis["positives"]))
        self.assertTrue(any("otomatik ucuz/pahalı" in item for item in synthesis["context"]))

    def test_corporate_event_category_does_not_change_directional_state(self):
        report = build_equity_report_contract(
            symbol="SASA",
            corporate_events=[
                {
                    "published_at": "2026-09-05T18:30:00+03:00",
                    "category": "CAPITAL_ACTION",
                    "category_label": "Sermaye işlemi",
                    "title": "Bedelli Sermaye Artırımı Hakkında",
                    "direction": "NOT_INFERRED",
                }
            ],
        )
        synthesis = report["integrated_synthesis"]
        self.assertEqual(synthesis["state"], "INSUFFICIENT_OR_NEUTRAL")
        self.assertFalse(synthesis["positives"])
        self.assertFalse(synthesis["risks"])
        self.assertTrue(synthesis["decision_contract"]["corporate_event_category_is_not_sentiment"])
        self.assertTrue(any("olumlu/olumsuz" in item for item in synthesis["context"]))

    def test_preview_contains_separate_axes_and_no_auto_trade(self):
        report = build_equity_report_contract(
            symbol="SAHOL",
            technical_report={"technical_synthesis": {"state": "MIXED"}},
            current_fundamental_view={
                "available": True,
                "synthesis": {"state": "MIXED_BALANCE_STRONGER_THAN_EARNINGS_QUALITY"},
            },
        )
        text = format_equity_report_preview(report)
        self.assertIn("V4 Bütünleşik Hisse Analizi", text)
        self.assertIn("otomatik AL/SAT", text)
        self.assertTrue(report["data_contract"]["no_single_score"])


if __name__ == "__main__":
    unittest.main()
