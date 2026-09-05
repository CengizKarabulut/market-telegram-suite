import unittest

from market_core.technical_synthesis import build_technical_synthesis


class TechnicalSynthesisTests(unittest.TestCase):
    def _features(self, short_state: str, momentum: str = "MIXED") -> dict:
        return {
            "available": True,
            "sections": {
                "trend_and_averages": {
                    "state": "MIXED",
                    "short_ma": {"state": short_state},
                },
                "momentum": {"state": momentum},
                "participation": {"state": "NORMAL_PARTICIPATION"},
            },
        }

    def test_bullish_short_ma_inside_bearish_structure_is_early_recovery(self) -> None:
        result = build_technical_synthesis(
            structure={"bias": "BEARISH", "price_position": "INSIDE_STRUCTURE"},
            technical_features=self._features("BULLISH_ALIGNMENT", "POSITIVE"),
            scanner_evidence=[],
            ma_level_evidence=[],
            evidence_summary={"directional_bias": -0.2, "clarity": 0.8},
        )
        self.assertEqual(result["state"], "EARLY_RECOVERY")
        self.assertTrue(result["conflicts"])
        self.assertIn("trend dönüşü", result["conflicts"][0])

    def test_historical_buy_signal_does_not_become_live_buy_context(self) -> None:
        result = build_technical_synthesis(
            structure={"bias": "TRANSITION", "price_position": "INSIDE_STRUCTURE"},
            technical_features=self._features("MIXED"),
            scanner_evidence=[{"side": "BUY", "state": "HISTORICAL"}],
            ma_level_evidence=[],
            evidence_summary={"directional_bias": 0.0, "clarity": 0.7},
        )
        self.assertEqual(result["live_scanner_sides"], [])
        self.assertEqual(result["historical_scanner_count"], 1)
        self.assertFalse(any("güncel AL" in item for item in result["positives"]))

    def test_live_buy_in_bearish_structure_is_explicit_conflict(self) -> None:
        result = build_technical_synthesis(
            structure={"bias": "BEARISH", "price_position": "BELOW_STRUCTURE"},
            technical_features=self._features("MIXED"),
            scanner_evidence=[{"side": "BUY", "state": "ACTIVE"}],
            ma_level_evidence=[],
            evidence_summary={"directional_bias": -0.4, "clarity": 0.8},
        )
        self.assertIn("BUY", result["live_scanner_sides"])
        self.assertTrue(any("yapı teyidi eksik" in item for item in result["conflicts"]))

    def test_near_ma_resistance_limits_positive_short_term_read(self) -> None:
        result = build_technical_synthesis(
            structure={"bias": "TRANSITION", "price_position": "INSIDE_STRUCTURE"},
            technical_features=self._features("BULLISH_ALIGNMENT", "POSITIVE"),
            scanner_evidence=[],
            ma_level_evidence=[{"side": "RESISTANCE", "distance_atr": 0.45}],
            evidence_summary={"directional_bias": 0.1, "clarity": 0.8},
        )
        self.assertTrue(any("MA direnci" in item for item in result["conflicts"]))


if __name__ == "__main__":
    unittest.main()
