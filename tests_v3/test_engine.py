import unittest

import pandas as pd

from market_core import build_market_state
from market_core.models import EvidenceDirection


class MarketStateEngineTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        close = [
            21.0, 22.0, 23.5, 22.8, 21.7, 22.5, 24.2, 23.4, 22.0, 23.1,
            25.0, 24.0, 22.6, 23.8, 25.8, 24.8, 23.2, 24.1, 26.3, 25.1,
        ]
        return pd.DataFrame(
            {
                "Open": [value - 0.2 for value in close],
                "High": [value + 0.6 for value in close],
                "Low": [value - 0.6 for value in close],
                "Close": close,
                "ATR": [1.0] * len(close),
                "Volume": [1_000_000] * len(close),
            },
            index=pd.bdate_range("2026-08-03", periods=len(close)),
        )

    def test_engine_returns_one_canonical_state(self) -> None:
        state = build_market_state(
            self._frame(),
            "TEST",
            "1d",
            indicators={"RSI": 58.0, "MACD_HIST": 0.20, "SMI": 12.0, "RVOL": 1.1},
        )
        self.assertEqual(state.symbol, "TEST")
        self.assertEqual(state.interval, "1d")
        self.assertEqual(state.price, 25.1)
        self.assertIn("pivots", state.structure)
        self.assertIn("nearest_levels", state.structure)
        self.assertIsInstance(state.levels, list)
        self.assertIsInstance(state.scenarios, list)
        self.assertTrue(state.interpretation["available"])
        self.assertTrue(state.evidence)
        self.assertIn("clarity", state.evidence_summary)
        for scenario in state.scenarios:
            self.assertEqual(str(scenario["state"].value), "PENDING")

    def test_low_rvol_is_uncertainty_not_bearish(self) -> None:
        state = build_market_state(
            self._frame(),
            "TEST",
            "1d",
            indicators={"RSI": 58.0, "MACD_HIST": 0.20, "SMI": 12.0, "RVOL": 0.55},
        )
        participation = [item for item in state.evidence if item.family == "participation"]
        self.assertEqual(len(participation), 1)
        self.assertEqual(participation[0].direction, EvidenceDirection.UNCERTAINTY)
        self.assertNotEqual(participation[0].direction, EvidenceDirection.BEARISH)

    def test_momentum_indicators_are_one_family_not_three_votes(self) -> None:
        state = build_market_state(
            self._frame(),
            "TEST",
            "1d",
            indicators={"RSI": 62.0, "MACD_HIST": 0.3, "SMI": 18.0, "RVOL": 1.0},
        )
        momentum = [item for item in state.evidence if item.independent_group == "momentum"]
        self.assertEqual(len(momentum), 1)
        self.assertEqual(momentum[0].direction, EvidenceDirection.BULLISH)

    def test_critical_data_quality_hard_gates_interpretation(self) -> None:
        state = build_market_state(
            self._frame(),
            "TEST",
            "1d",
            data_quality={"state": "CRITICAL", "reason": "corporate action suspect"},
            indicators={"RSI": 60.0, "MACD_HIST": 0.2, "SMI": 10.0, "RVOL": 1.2},
        )
        self.assertTrue(state.confidence["critical_data_quality"])
        self.assertTrue(state.limitations)
        self.assertFalse(state.interpretation["available"])
        self.assertEqual(state.interpretation["up_scenario"], [])
        self.assertEqual(state.interpretation["down_scenario"], [])

    def test_missing_ohlc_is_rejected(self) -> None:
        bad = self._frame().drop(columns=["Low"])
        with self.assertRaisesRegex(ValueError, "Low"):
            build_market_state(bad, "TEST", "1d")


if __name__ == "__main__":
    unittest.main()
