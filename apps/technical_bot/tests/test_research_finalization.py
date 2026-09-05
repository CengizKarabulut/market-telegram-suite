from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.fundamental_analysis import Factor, FundamentalReport
from src.research_risk import _quality_dimension, _risk_engine
from src.research_technical import _elliott_context, _structure_event


class ResearchFinalizationTests(unittest.TestCase):
    def test_company_quality_excludes_valuation_factor(self) -> None:
        fundamental = FundamentalReport(
            symbol="TEST",
            company_name="Test",
            price=100.0,
            sector="Industrials",
            profile="GENERIC",
            overall_score=3.0,
            coverage=1.0,
            factors=(
                Factor("Değerleme", 1.0, 1.0, ""),
                Factor("Büyüme", 5.0, 1.0, ""),
                Factor("Kârlılık", 5.0, 1.0, ""),
                Factor("Bilanço Sağlığı", 5.0, 1.0, ""),
                Factor("Nakit Akışı", 5.0, 1.0, ""),
            ),
            positives=(),
            risks=(),
            metrics={},
            note="",
        )
        dimension = _quality_dimension(SimpleNamespace(fundamental=fundamental))
        self.assertEqual(dimension.score, 100.0)
        self.assertEqual(dimension.coverage, 1.0)

    def test_missing_evidence_does_not_create_fake_risk(self) -> None:
        main, risks = _risk_engine(
            "GENERIC",
            {"metrics": {}, "earnings_quality_score": None, "earnings_quality_coverage": 0.0},
            {"score": None, "coverage": 0.0},
            {"score": None, "average_turnover_20": None},
            (),
        )
        self.assertIsNone(main)
        self.assertEqual(risks, ())

    def test_downtrend_breaking_last_lower_high_is_upward_choch(self) -> None:
        structure = {
            "state": "LH / LL",
            "bos": "Swing High üzeri BOS",
            "last_high": {"label": "LH", "price": 110.0},
            "last_low": {"label": "LL", "price": 90.0},
        }
        self.assertEqual(_structure_event(structure), "CHoCH YUKARI")

    def test_uptrend_breaking_last_higher_low_is_downward_choch(self) -> None:
        structure = {
            "state": "HH / HL",
            "bos": "Swing Low altı BOS",
            "last_high": {"label": "HH", "price": 120.0},
            "last_low": {"label": "HL", "price": 105.0},
        }
        self.assertEqual(_structure_event(structure), "CHoCH AŞAĞI")

    def test_elliott_stays_uncertain_with_too_few_confirmed_swings(self) -> None:
        result = _elliott_context(
            [
                {"type": "low", "price": 90.0},
                {"type": "high", "price": 100.0},
                {"type": "low", "price": 95.0},
            ],
            {"state": "HH / HL", "bos": "Yeni yapı kırılımı yok"},
        )
        self.assertEqual(result["primary"], "BELİRSİZ")
        self.assertLess(result["confidence"], 50)


if __name__ == "__main__":
    unittest.main()
