import unittest

from market_core.fundamental_models import SectorType
from market_core.peer_benchmarks import (
    PeerObservation,
    build_hierarchical_peer_benchmark,
    build_peer_benchmark,
)


class PeerBenchmarkTests(unittest.TestCase):
    def _gyo_rows(self):
        return [
            PeerObservation("ZGYO", "BIST_GYO", SectorType.GYO, {"ltv": 0.03, "roe": 0.18}),
            PeerObservation("A", "BIST_GYO", SectorType.GYO, {"ltv": 0.10, "roe": 0.12}),
            PeerObservation("B", "BIST_GYO", SectorType.GYO, {"ltv": 0.20, "roe": 0.15}),
            PeerObservation("C", "BIST_GYO", SectorType.GYO, {"ltv": 0.35, "roe": 0.09}),
            PeerObservation("D", "BIST_GYO", SectorType.GYO, {"ltv": 0.50, "roe": 0.11}),
            PeerObservation("E", "BIST_GYO", SectorType.GYO, {"ltv": 0.65, "roe": 0.07}),
        ]

    def test_target_is_excluded_and_low_ltv_is_favourable(self):
        result = build_peer_benchmark(
            target_symbol="ZGYO",
            peer_group="BIST_GYO",
            sector_type=SectorType.GYO,
            observations=self._gyo_rows(),
        )
        ltv = result["metrics"]["ltv"]
        self.assertTrue(ltv["available"])
        self.assertEqual(ltv["peer_count"], 5)
        self.assertEqual(ltv["position"], "BOTTOM_QUARTILE")
        self.assertEqual(ltv["favourability"], "FAVOURABLE")
        self.assertTrue(result["quality"]["target_excluded_from_peer_stats"])

    def test_mean_is_exposed_but_quartiles_drive_location(self):
        rows = [
            PeerObservation("T", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 2.0}),
            PeerObservation("A", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 1.0}),
            PeerObservation("B", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 1.2}),
            PeerObservation("C", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 1.4}),
            PeerObservation("D", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 1.6}),
            PeerObservation("E", "IND", SectorType.INDUSTRIAL, {"net_debt_to_ebitda": 20.0}),
        ]
        result = build_peer_benchmark(
            target_symbol="T",
            peer_group="IND",
            sector_type=SectorType.INDUSTRIAL,
            observations=rows,
        )
        metric = result["metrics"]["net_debt_to_ebitda"]
        self.assertGreater(metric["peer_mean"], metric["peer_median"])
        self.assertEqual(metric["position"], "TOP_QUARTILE")
        self.assertEqual(metric["favourability"], "UNFAVOURABLE")

    def test_insufficient_peer_count_fails_closed(self):
        rows = [
            PeerObservation("T", "BANK", SectorType.BANK, {"roe": 0.20}),
            PeerObservation("A", "BANK", SectorType.BANK, {"roe": 0.15}),
            PeerObservation("B", "BANK", SectorType.BANK, {"roe": 0.16}),
        ]
        result = build_peer_benchmark(
            target_symbol="T",
            peer_group="BANK",
            sector_type=SectorType.BANK,
            observations=rows,
        )
        self.assertFalse(result["metrics"]["roe"]["available"])
        self.assertEqual(result["synthesis"]["state"], "INSUFFICIENT_PEER_DATA")

    def test_contextual_valuation_metric_is_not_called_good_or_bad(self):
        rows = [
            PeerObservation("T", "BIST_GYO", SectorType.GYO, {"price_to_nav": 0.55}),
            PeerObservation("A", "BIST_GYO", SectorType.GYO, {"price_to_nav": 0.60}),
            PeerObservation("B", "BIST_GYO", SectorType.GYO, {"price_to_nav": 0.70}),
            PeerObservation("C", "BIST_GYO", SectorType.GYO, {"price_to_nav": 0.80}),
            PeerObservation("D", "BIST_GYO", SectorType.GYO, {"price_to_nav": 0.90}),
            PeerObservation("E", "BIST_GYO", SectorType.GYO, {"price_to_nav": 1.00}),
        ]
        result = build_peer_benchmark(
            target_symbol="T",
            peer_group="BIST_GYO",
            sector_type=SectorType.GYO,
            observations=rows,
        )
        metric = result["metrics"]["price_to_nav"]
        self.assertTrue(metric["available"])
        self.assertEqual(metric["favourability"], "CONTEXTUAL")

    def test_wrong_peer_group_is_not_mixed_into_stats(self):
        rows = self._gyo_rows() + [
            PeerObservation("BANK1", "BIST_BANK", SectorType.BANK, {"roe": 0.80}),
            PeerObservation("OTHERGYO", "OTHER_GYO", SectorType.GYO, {"ltv": 0.99}),
        ]
        result = build_peer_benchmark(
            target_symbol="ZGYO",
            peer_group="BIST_GYO",
            sector_type=SectorType.GYO,
            observations=rows,
        )
        self.assertEqual(result["metrics"]["ltv"]["peer_count"], 5)

    def test_declared_metric_basis_must_match(self):
        rows = [
            PeerObservation(
                "T",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 0.20},
                metric_basis={"revenue_growth": "TTM"},
            ),
            PeerObservation(
                "A",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 0.10},
                metric_basis={"revenue_growth": "TTM"},
            ),
            PeerObservation(
                "B",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 0.12},
                metric_basis={"revenue_growth": "TTM"},
            ),
            PeerObservation(
                "C",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 0.13},
                metric_basis={"revenue_growth": "TTM"},
            ),
            PeerObservation(
                "D",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 0.14},
                metric_basis={"revenue_growth": "TTM"},
            ),
            PeerObservation(
                "YTD1",
                "IND",
                SectorType.INDUSTRIAL,
                {"revenue_growth": 9.99},
                metric_basis={"revenue_growth": "CURRENT_PROVIDER_COMPARATIVE:2025Q2"},
            ),
        ]
        result = build_peer_benchmark(
            target_symbol="T",
            peer_group="IND",
            sector_type=SectorType.INDUSTRIAL,
            observations=rows,
        )
        metric = result["metrics"]["revenue_growth"]
        self.assertTrue(metric["available"])
        self.assertEqual(metric["peer_count"], 4)
        self.assertEqual(metric["basis_excluded_count"], 1)
        self.assertEqual(metric["basis"], "TTM")

    def test_hierarchical_benchmark_explicitly_falls_back_to_broad_sector(self):
        rows = [
            PeerObservation("T", "AIRLINES", SectorType.INDUSTRIAL, {"roe": 0.20}),
            PeerObservation("A", "AIRLINES", SectorType.INDUSTRIAL, {"roe": 0.15}),
            PeerObservation("B", "AIRLINES", SectorType.INDUSTRIAL, {"roe": 0.16}),
            PeerObservation("C", "MACHINERY", SectorType.INDUSTRIAL, {"roe": 0.11}),
            PeerObservation("D", "MACHINERY", SectorType.INDUSTRIAL, {"roe": 0.12}),
            PeerObservation("E", "RETAIL", SectorType.INDUSTRIAL, {"roe": 0.13}),
            PeerObservation("F", "RETAIL", SectorType.INDUSTRIAL, {"roe": 0.14}),
        ]
        result = build_hierarchical_peer_benchmark(
            target_symbol="T",
            peer_group="AIRLINES",
            sector_type=SectorType.INDUSTRIAL,
            observations=rows,
        )
        self.assertFalse(result["industry_benchmark"]["metrics"]["roe"]["available"])
        self.assertTrue(result["metrics"]["roe"]["available"])
        self.assertEqual(result["metrics"]["roe"]["scope"], "BROAD_SECTOR_FALLBACK")
        self.assertIn("roe", result["fallback_metrics"])


if __name__ == "__main__":
    unittest.main()
