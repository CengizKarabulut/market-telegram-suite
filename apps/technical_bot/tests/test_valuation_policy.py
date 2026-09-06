from __future__ import annotations

import unittest

from src.valuation_policy import build_valuation_policy


PEER = {
    "score": 55.0,
    "coverage": 0.75,
    "scope": "Finance sektörü",
    "metrics": {"pb": {"value": 1.2, "percentile": 50.0}},
}


class ValuationPolicyTests(unittest.TestCase):
    def _by_model(self, report):
        return {item["model"]: item for item in report["models"]}

    def test_gyo_uses_nav_primary_and_does_not_fabricate_it(self) -> None:
        report = build_valuation_policy(
            "GYO",
            "Real Estate",
            {"cfo_net_income": None, "fcf_margin": None},
            PEER,
            20.0,
        )
        models = self._by_model(report)
        self.assertEqual(report["primary_model"], "NAD / NAV")
        self.assertEqual(models["NAD / NAV"]["status"], "VERİ EKSİK")
        self.assertEqual(models["F/K"]["status"], "UYGUN DEĞİL")
        self.assertEqual(report["computed_values"], {})

    def test_bank_rejects_fcff_and_prefers_equity_models(self) -> None:
        report = build_valuation_policy(
            "BANK",
            "Banks",
            {"roe": 25.0, "pb": 1.5},
            PEER,
            50.0,
        )
        models = self._by_model(report)
        self.assertIn("Residual Income", report["primary_model"])
        self.assertEqual(models["Residual Income"]["status"], "KOŞULLU")
        self.assertEqual(models["FCFF / FD-FAVÖK"]["status"], "UYGUN DEĞİL")
        self.assertEqual(models["Altman Z"]["status"], "UYGUN DEĞİL")

    def test_generic_positive_cash_conversion_allows_conditional_dcf(self) -> None:
        report = build_valuation_policy(
            "GENERIC",
            "Industrials",
            {"cfo_net_income": 1.15, "fcf_margin": 12.0, "operating_growth": 8.0},
            PEER,
            100.0,
        )
        models = self._by_model(report)
        self.assertEqual(report["primary_model"], "FCFF DCF")
        self.assertEqual(models["FCFF DCF"]["status"], "KOŞULLU")
        self.assertIsNone(models["FCFF DCF"]["value_per_share"])
        self.assertEqual(report["computed_values"], {})

    def test_holding_requires_sotp_inputs(self) -> None:
        report = build_valuation_policy(
            "GENERIC",
            "Investment Holding Companies",
            {"cfo_net_income": 1.0, "fcf_margin": 5.0, "operating_growth": 5.0},
            PEER,
            10.0,
        )
        models = self._by_model(report)
        self.assertEqual(report["primary_model"], "NAD / SOTP")
        self.assertEqual(models["NAD / SOTP"]["status"], "VERİ EKSİK")


if __name__ == "__main__":
    unittest.main()
