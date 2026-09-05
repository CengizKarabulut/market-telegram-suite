import unittest

import pandas as pd

from market_core.engine import build_market_state
from market_core.external_evidence import (
    ma_level_from_mapping,
    ma_level_to_technical_level,
    scan_signal_from_mapping,
)
from market_core.levels import wave_levels
from market_core.models import WaveHypothesis


class ExternalEvidenceAdapterTests(unittest.TestCase):
    def test_taramabot_signal_is_normalized_without_becoming_direct_trade_decision(self) -> None:
        signal = scan_signal_from_mapping(
            {
                "signal_code": "S-M-V-1",
                "ticker": "ASELS",
                "timeframe": "4H",
                "signal": "AL",
                "status": "aktif",
                "bars_since": 2,
                "matched_conditions": ["SMI yukari", "MACD histogram", "hacim"],
            }
        )
        self.assertEqual(signal.scanner_code, "S-M-V-1")
        self.assertEqual(signal.symbol, "ASELS")
        self.assertEqual(signal.timeframe, "4h")
        self.assertEqual(signal.side, "BUY")
        self.assertEqual(signal.state, "ACTIVE")
        self.assertEqual(signal.age_bars, 2)

    def test_ma_watchlist_zone_becomes_observed_support(self) -> None:
        evidence = ma_level_from_mapping(
            {
                "symbol": "ZGYO",
                "timeframe": "1d",
                "side": "Destek",
                "zone_low": 20.80,
                "zone_high": 21.10,
                "zone_mid": 20.95,
                "distance_atr": -0.20,
                "ma_list": "EMA50, KAMA55",
                "level_touches": 14,
                "hold_rate_pct": 79.0,
                "median_bounce_atr": 1.6,
                "zone_score": 52.0,
                "zone_quality": "Guclu",
                "zone_member_count": 2,
            }
        )
        level = ma_level_to_technical_level(evidence, price=21.0)
        self.assertIsNotNone(level)
        assert level is not None
        self.assertEqual(level.source, "MA_OBSERVED_LEVEL")
        self.assertEqual(level.role, "SUPPORT")
        self.assertEqual(level.zone_low, 20.80)
        self.assertEqual(level.zone_high, 21.10)
        self.assertEqual(level.tests, 14)
        self.assertEqual(level.metadata["ma_list"], ["EMA50", "KAMA55"])

    def test_completed_abc_does_not_create_live_wave_level(self) -> None:
        hypothesis = WaveHypothesis(
            id="abc-complete",
            timeframe="1d",
            degree="minor",
            pattern_type="ABC_ZIGZAG",
            direction="UP",
            pivot_indices=[1, 2, 3, 4],
            active_wave="ABC_COMPLETE",
            confidence=0.60,
            hard_rule_valid=True,
            soft_score=0.50,
            invalidation_level=19.19,
            target_zones=[],
        )
        self.assertEqual(wave_levels([hypothesis], price=21.0, atr=1.0), [])


class MarketStateIntegrationTests(unittest.TestCase):
    @staticmethod
    def _data() -> pd.DataFrame:
        values = [20.0, 20.4, 20.2, 20.8, 20.5, 21.0, 20.7, 21.2, 21.0, 21.3, 21.1, 21.4]
        return pd.DataFrame(
            {
                "Open": values,
                "High": [value + 0.3 for value in values],
                "Low": [value - 0.3 for value in values],
                "Close": values,
                "ATR": [1.0] * len(values),
            },
            index=pd.date_range("2026-08-01", periods=len(values), freq="D"),
        )

    def test_same_timeframe_ma_zone_enters_unified_level_engine(self) -> None:
        state = build_market_state(
            self._data(),
            "ZGYO",
            "1d",
            scanner_rows=[
                {
                    "signal_code": "S-M-V-1",
                    "symbol": "ZGYO",
                    "timeframe": "4H",
                    "signal": "AL",
                }
            ],
            ma_level_rows=[
                {
                    "symbol": "ZGYO",
                    "timeframe": "1d",
                    "side": "Destek",
                    "zone_low": 20.80,
                    "zone_high": 21.00,
                    "zone_mid": 20.90,
                    "distance_atr": -0.50,
                    "ma_list": "EMA50, KAMA55",
                    "level_touches": 12,
                    "zone_score": 48.0,
                    "zone_quality": "Guclu",
                },
                {
                    "symbol": "ZGYO",
                    "timeframe": "4h",
                    "side": "Direnc",
                    "zone_low": 22.00,
                    "zone_high": 22.20,
                    "zone_mid": 22.10,
                    "distance_atr": 0.80,
                    "ma_list": "SMA200",
                    "level_touches": 10,
                    "zone_score": 45.0,
                },
            ],
        )
        ma_levels = [level for level in state.levels if level.source == "MA_OBSERVED_LEVEL"]
        self.assertEqual(len(ma_levels), 1)
        self.assertAlmostEqual(ma_levels[0].value, 20.90)
        self.assertEqual(len(state.scanner_evidence), 1)
        self.assertEqual(len(state.ma_level_evidence), 2)
        self.assertTrue(state.confidence["scanner_evidence_available"])
        self.assertTrue(state.confidence["ma_level_evidence_available"])


if __name__ == "__main__":
    unittest.main()
