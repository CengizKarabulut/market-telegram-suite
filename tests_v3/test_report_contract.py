import json
import unittest

import pandas as pd

from market_core import build_market_state
from market_core.report import build_report_contract, format_telegram_preview
from market_core.serialization import market_state_json, report_json


class ReportContractTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        close = [20.0, 20.8, 21.6, 21.1, 20.5, 21.3, 22.1, 21.4, 20.9, 21.8, 22.7, 22.0, 21.3, 22.2, 23.0, 22.5, 21.9, 22.6, 23.5, 23.1]
        return pd.DataFrame(
            {
                "Open": [value - 0.15 for value in close],
                "High": [value + 0.45 for value in close],
                "Low": [value - 0.45 for value in close],
                "Close": close,
                "ATR": [0.8] * len(close),
                "ADX": [28.0] * len(close),
                "EMA20": [21.0] * len(close),
                "EMA50": [20.0] * len(close),
                "Volume": [1_000_000] * len(close),
            },
            index=pd.bdate_range("2026-08-03", periods=len(close)),
        )

    def test_report_contract_is_interval_aware(self) -> None:
        state = build_market_state(self._frame(), "TEST", "4h", indicators={"ADX": 28, "EMA20": 21, "EMA50": 20})
        report = build_report_contract(state)
        self.assertEqual(report["interval_label"], "4 saatlik")
        self.assertEqual(report["language_contract"]["close_noun"], "4 saatlik kapanış")
        self.assertTrue(report["language_contract"]["forbid_generic_daily_wording"])
        preview = format_telegram_preview(report)
        self.assertIn("4 saatlik", preview)
        self.assertNotIn("günlük kapanış", preview)

    def test_json_serialization_rejects_nan_by_normalizing_it(self) -> None:
        state = build_market_state(self._frame(), "TEST", "1d", indicators={"RSI": float("nan")})
        state_payload = json.loads(market_state_json(state))
        report_payload = json.loads(report_json(build_report_contract(state)))
        self.assertEqual(state_payload["schema"], "market-state/v3")
        self.assertEqual(report_payload["schema"], "market-report/v3")
        self.assertIsNone(state_payload["indicators"]["RSI"])

    def test_critical_quality_blocks_report_analysis(self) -> None:
        state = build_market_state(
            self._frame(),
            "TEST",
            "1d",
            data_quality={"state": "CRITICAL", "critical": True},
        )
        report = build_report_contract(state)
        self.assertFalse(report["availability"]["analysis"])
        self.assertIn("veri kalitesi", format_telegram_preview(report).lower())


if __name__ == "__main__":
    unittest.main()
