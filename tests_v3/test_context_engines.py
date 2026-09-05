import unittest

import pandas as pd

from market_core.multi_timeframe import build_multi_timeframe
from market_core.regime import build_regime
from market_core.relative_strength import build_relative_strength
from market_core.structure import swing_level_from_pivot
from market_core.models import LevelLifecycle, Pivot


class ContextEngineTests(unittest.TestCase):
    def _trend_frame(self) -> pd.DataFrame:
        close = [100 + i * 1.5 for i in range(30)]
        return pd.DataFrame(
            {
                "Open": [v - 0.4 for v in close],
                "High": [v + 0.8 for v in close],
                "Low": [v - 0.8 for v in close],
                "Close": close,
                "ATR": [2.0] * len(close),
                "ADX": [30.0] * len(close),
                "EMA20": [95 + i * 1.45 for i in range(30)],
                "EMA50": [90 + i * 1.35 for i in range(30)],
                "BB_WIDTH": [0.12] * len(close),
            },
            index=pd.bdate_range("2026-07-01", periods=len(close)),
        )

    def test_directional_regime_detected(self) -> None:
        regime = build_regime(self._trend_frame())
        self.assertEqual(regime["state"], "DIRECTIONAL_TREND_UP")
        self.assertGreater(regime["confidence"], 0.7)

    def test_relative_strength_outperformance(self) -> None:
        frame = self._trend_frame()
        benchmark = frame.copy()
        benchmark["Close"] = [100 + i * 0.5 for i in range(len(frame))]
        rs = build_relative_strength(frame, benchmark, benchmark_name="XU100")
        self.assertTrue(rs["available"])
        self.assertEqual(rs["state"], "OUTPERFORMING")
        self.assertEqual(rs["direction"], "BULLISH")

    def test_mtf_divergence_is_uncertainty(self) -> None:
        mtf = build_multi_timeframe(
            "1h",
            {
                "4h": {"bias": "BULLISH", "clarity": 0.8},
                "1d": {"bias": "BEARISH", "clarity": 0.8},
            },
        )
        self.assertTrue(mtf["available"])
        self.assertEqual(mtf["state"], "DIVERGENT")
        self.assertEqual(mtf["direction"], "UNCERTAINTY")


class LifecycleSemanticsTests(unittest.TestCase):
    def test_broken_support_retest_rejection_is_not_plain_broken(self) -> None:
        close = [30.0, 29.5, 28.5, 27.7, 27.2, 27.8, 27.5, 26.9]
        data = pd.DataFrame(
            {
                "Open": close,
                "High": [v + 0.5 for v in close],
                "Low": [v - 0.5 for v in close],
                "Close": close,
                "ATR": [1.0] * len(close),
            },
            index=pd.bdate_range("2026-08-01", periods=len(close)),
        )
        pivot = Pivot(index=1, timestamp=data.index[1], price=28.0, kind="LOW", confirmed_index=2)
        level = swing_level_from_pivot(pivot, price=float(data["Close"].iloc[-1]), last_index=len(data) - 1, data=data)
        self.assertEqual(level.lifecycle_state, LevelLifecycle.REJECTED)
        self.assertIn("SUPPORT", level.role)
        self.assertTrue(level.metadata["lifecycle_events"])


if __name__ == "__main__":
    unittest.main()
