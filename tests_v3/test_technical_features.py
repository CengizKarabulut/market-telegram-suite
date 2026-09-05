import unittest

import pandas as pd

from market_core.technical_features import build_technical_features


class TechnicalFeatureTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        index = pd.bdate_range("2026-08-01", periods=12)
        close = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8, 12.0, 12.2]
        frame = pd.DataFrame({"Close": close}, index=index)
        frame["EMA_5"] = [9.9, 10.0, 10.1, 10.2, 10.3, 10.5, 10.7, 10.9, 11.1, 11.3, 11.5, 11.9]
        frame["EMA_8"] = [9.8, 9.9, 10.0, 10.1, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.7]
        frame["EMA_13"] = [9.7, 9.8, 9.9, 10.0, 10.1, 10.3, 10.5, 10.7, 10.9, 11.1, 11.3, 11.5]
        frame["EMA_20"] = [9.5 + i * 0.12 for i in range(12)]
        frame["EMA_50"] = [9.0 + i * 0.10 for i in range(12)]
        frame["RSI"] = [48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60]
        frame["SMI"] = [-5, -4, -3, -2, 0, 2, 4, 6, 8, 10, 12, 15]
        frame["SMI_EMA"] = [-4, -4, -3, -2, -1, 1, 3, 5, 7, 9, 11, 13]
        frame["MACD_HIST"] = [-0.2, -0.1, -0.05, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
        frame["VOLUME_RATIO"] = [1.0] * 11 + [1.7]
        frame["ADX"] = [20.0] * 11 + [28.0]
        frame["PLUS_DI"] = [20.0] * 11 + [30.0]
        frame["MINUS_DI"] = [20.0] * 11 + [15.0]
        frame["BB_WIDTH_RANK"] = [50.0] * 12
        return frame

    def test_short_ema_alignment_requires_order_slope_and_price_position(self) -> None:
        result = build_technical_features(self._frame())
        short = result["sections"]["trend_and_averages"]["short_ma"]
        self.assertEqual(short["arrangement"], "5>8>13")
        self.assertEqual(short["state"], "BULLISH_ALIGNMENT")
        self.assertIn("pozitif sıralı", short["interpretation"])

    def test_momentum_and_participation_are_separate_sections(self) -> None:
        result = build_technical_features(self._frame())
        momentum = result["sections"]["momentum"]
        participation = result["sections"]["participation"]
        self.assertEqual(momentum["state"], "POSITIVE")
        self.assertEqual(momentum["macd_hist_state"], "POSITIVE_AND_EXPANDING")
        self.assertEqual(participation["state"], "STRONG_PARTICIPATION")

    def test_low_volume_is_not_described_as_bearish_direction(self) -> None:
        frame = self._frame()
        frame.loc[frame.index[-1], "VOLUME_RATIO"] = 0.5
        result = build_technical_features(frame)
        participation = result["sections"]["participation"]
        self.assertEqual(participation["state"], "LOW_PARTICIPATION")
        self.assertIn("güvenini azaltıyor", participation["interpretation"])

    def test_missing_short_ma_data_stays_insufficient(self) -> None:
        frame = self._frame().drop(columns=["EMA_5", "EMA_8", "EMA_13"])
        result = build_technical_features(frame)
        short = result["sections"]["trend_and_averages"]["short_ma"]
        self.assertEqual(short["state"], "INSUFFICIENT")


if __name__ == "__main__":
    unittest.main()
