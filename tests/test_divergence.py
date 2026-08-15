import unittest

import numpy as np
import pandas as pd

from src.divergence import detect_divergences


def divergence_frame(bullish: bool = True) -> pd.DataFrame:
    rows = 45
    index = pd.date_range("2025-01-01", periods=rows, freq="B")
    low = np.full(rows, 100.0)
    high = np.full(rows, 110.0)
    if bullish:
        low[[10, 25]] = [90.0, 85.0]
        rsi = np.full(rows, 50.0)
        macd = np.zeros(rows)
        smi = np.zeros(rows)
        rsi[[10, 25]] = [30.0, 40.0]
        macd[[10, 25]] = [-2.0, -1.0]
        smi[[10, 25]] = [-40.0, -30.0]
    else:
        high[[10, 25]] = [120.0, 125.0]
        rsi = np.full(rows, 50.0)
        macd = np.zeros(rows)
        smi = np.zeros(rows)
        rsi[[10, 25]] = [70.0, 60.0]
        macd[[10, 25]] = [2.0, 1.0]
        smi[[10, 25]] = [40.0, 30.0]
    return pd.DataFrame({"Low": low, "High": high, "RSI": rsi, "MACD": macd, "SMI": smi}, index=index)


class DivergenceTests(unittest.TestCase):
    def test_regular_bullish_matches_tradingview_rsi_semantics(self) -> None:
        result = detect_divergences(divergence_frame(True))
        for name in ("RSI", "MACD", "SMI"):
            item = result["indicators"][name]
            self.assertTrue(item["detected"])
            self.assertEqual(item["state"], "Pozitif normal uyumsuzluk")
            self.assertEqual(item["pivot_relation"], "LL / HL")
            self.assertEqual(item["event_age"], 14)

    def test_regular_bearish_matches_tradingview_rsi_semantics(self) -> None:
        result = detect_divergences(divergence_frame(False))
        for name in ("RSI", "MACD", "SMI"):
            item = result["indicators"][name]
            self.assertTrue(item["detected"])
            self.assertEqual(item["state"], "Negatif normal uyumsuzluk")
            self.assertEqual(item["pivot_relation"], "HH / LH")

    def test_right_lookback_delays_confirmation(self) -> None:
        full = divergence_frame(True)
        before_confirmation = full.iloc[:30]
        at_confirmation = full.iloc[:31]
        self.assertFalse(detect_divergences(before_confirmation)["indicators"]["RSI"]["detected"])
        self.assertTrue(detect_divergences(at_confirmation)["indicators"]["RSI"]["detected"])
        self.assertEqual(detect_divergences(at_confirmation)["indicators"]["RSI"]["event_age"], 0)

    def test_pivots_outside_range_are_not_compared(self) -> None:
        data = divergence_frame(True)
        data.loc[:, ["RSI", "MACD", "SMI"]] = [50.0, 0.0, 0.0]
        data.loc[data.index[[5, 40]], "RSI"] = [30.0, 40.0]
        data.loc[data.index[[5, 40]], "Low"] = [90.0, 85.0]
        result = detect_divergences(data, left=2, right=2, range_lower=5, range_upper=30)
        self.assertFalse(result["indicators"]["RSI"]["detected"])


if __name__ == "__main__":
    unittest.main()
