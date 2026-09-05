import json
import tempfile
import unittest
from pathlib import Path

from market_core.external_io import load_ma_watchlist_rows, load_taramabot_state_rows
from market_core.external_evidence import scan_signal_from_mapping


class ExternalIoTests(unittest.TestCase):
    def test_taramabot_state_history_is_never_claimed_as_current_match(self) -> None:
        payload = {
            "signal_history": [
                {
                    "symbol": "ZGYO",
                    "period": "4H",
                    "strategy": "i9",
                    "bar_time": "2026-09-04T14:00:00+03:00",
                    "detected_at": "2026-09-04T14:03:00+03:00",
                    "price": 21.30,
                    "is_full": True,
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = load_taramabot_state_rows(path, symbol="ZGYO")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["scanner_code"], "S-M-V-1")
        self.assertEqual(rows[0]["state"], "HISTORICAL")
        self.assertTrue(rows[0]["data_quality"]["current_match_unknown"])
        signal = scan_signal_from_mapping(rows[0])
        self.assertEqual(signal.state, "HISTORICAL")
        self.assertEqual(signal.side, "BUY")

    def test_ma_watchlist_loader_filters_symbol_without_recalculating_score(self) -> None:
        csv_text = (
            "symbol,timeframe,side,zone_low,zone_high,zone_mid,zone_score,zone_quality,ma_list\n"
            "ZGYO,1d,Destek,20.80,21.10,20.95,52.0,Guclu,EMA50 + KAMA55\n"
            "ASELS,1d,Destek,300,305,302.5,48.0,Orta,SMA200\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ma_watchlist.csv"
            path.write_text(csv_text, encoding="utf-8")
            rows = load_ma_watchlist_rows(path, symbol="ZGYO")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "ZGYO")
        self.assertEqual(rows[0]["zone_score"], "52.0")
        self.assertEqual(rows[0]["zone_quality"], "Guclu")


if __name__ == "__main__":
    unittest.main()
