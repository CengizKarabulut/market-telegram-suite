import unittest

import pandas as pd

from market_core.technical_changes import build_technical_changes
from market_core.technical_features import build_technical_features


class TechnicalChangeTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        index = pd.bdate_range("2026-08-01", periods=12)
        close = [10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.0, 11.2]
        frame = pd.DataFrame({"Close": close}, index=index)
        frame["EMA_5"] = [10.2] * 9 + [10.8, 10.95, 11.05]
        frame["EMA_8"] = [10.3] * 9 + [10.85, 11.0, 11.0]
        frame["EMA_13"] = [10.4] * 9 + [10.9, 11.02, 10.95]
        frame["EMA_20"] = [10.5] * 10 + [11.05, 11.10]
        frame["EMA_50"] = [10.6] * 10 + [11.10, 11.15]
        frame["RSI"] = [45.0] * 10 + [49.0, 52.0]
        frame["SMI"] = [-5.0] * 10 + [-2.0, 1.0]
        frame["SMI_EMA"] = [-4.0] * 10 + [-1.0, 0.0]
        frame["MACD_HIST"] = [-0.20] * 10 + [-0.15, -0.08]
        frame["VOLUME_RATIO"] = [0.9] * 10 + [0.7, 1.1]
        frame["ADX"] = [18.0] * 10 + [19.0, 22.0]
        frame["PLUS_DI"] = [18.0] * 10 + [19.0, 25.0]
        frame["MINUS_DI"] = [22.0] * 10 + [23.0, 20.0]
        frame["BB_WIDTH_RANK"] = [50.0] * 12
        return frame

    def test_detects_new_rsi_and_smi_crosses(self) -> None:
        frame = self._frame()
        changes = build_technical_changes(
            frame,
            current_features=build_technical_features(frame),
        )
        kinds = {item["kind"] for item in changes["events"]}
        self.assertIn("RSI_50_CROSS_UP", kinds)
        self.assertIn("SMI_CROSS_UP", kinds)
        self.assertTrue(changes["no_lookahead"])

    def test_previous_snapshot_does_not_see_last_bar(self) -> None:
        frame = self._frame()
        before = build_technical_changes(frame.iloc[:-1].copy())
        after = build_technical_changes(frame)
        before_kinds = {item["kind"] for item in before["events"]}
        after_kinds = {item["kind"] for item in after["events"]}
        self.assertNotIn("RSI_50_CROSS_UP", before_kinds)
        self.assertIn("RSI_50_CROSS_UP", after_kinds)

    def test_macd_improvement_is_not_called_bullish_trend_reversal(self) -> None:
        frame = self._frame()
        changes = build_technical_changes(frame)
        macd = next(
            item
            for item in changes["events"]
            if item["kind"] == "MACD_HIST_CHANGE"
        )
        self.assertEqual(macd["effect"], "POSITIVE")
        self.assertIn("hâlâ negatif", macd["message"])

    def test_insufficient_input_fails_closed(self) -> None:
        frame = self._frame().iloc[:1].copy()
        changes = build_technical_changes(frame)
        self.assertFalse(changes["available"])
        self.assertEqual(changes["events"], [])


if __name__ == "__main__":
    unittest.main()
