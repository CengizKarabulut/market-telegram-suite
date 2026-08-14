import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from src.bar_state import build_bar_state


class BarStateTests(unittest.TestCase):
    def test_bist_daily_bar_is_live_during_same_day_session(self) -> None:
        data = pd.DataFrame({"Close": [100]}, index=pd.DatetimeIndex(["2026-08-14 09:00"], tz="Europe/Istanbul"))
        now = datetime(2026, 8, 14, 14, 20, tzinfo=ZoneInfo("Europe/Istanbul"))
        result = build_bar_state(data, "BIST", "1d", now)
        self.assertTrue(result["is_live"])
        self.assertEqual(result["label"], "CANLI")

    def test_bist_daily_bar_remains_live_during_closing_session(self) -> None:
        data = pd.DataFrame({"Close": [100]}, index=pd.DatetimeIndex(["2026-08-14 09:00"], tz="Europe/Istanbul"))
        now = datetime(2026, 8, 14, 18, 5, tzinfo=ZoneInfo("Europe/Istanbul"))
        self.assertTrue(build_bar_state(data, "BIST", "1d", now)["is_live"])

    def test_bist_daily_bar_is_confirmed_after_close(self) -> None:
        data = pd.DataFrame({"Close": [100]}, index=pd.DatetimeIndex(["2026-08-14 09:00"], tz="Europe/Istanbul"))
        now = datetime(2026, 8, 14, 18, 10, tzinfo=ZoneInfo("Europe/Istanbul"))
        result = build_bar_state(data, "BIST", "1d", now)
        self.assertTrue(result["is_confirmed"])
        self.assertEqual(result["label"], "TEYİTLİ")

    def test_previous_session_bar_is_confirmed(self) -> None:
        data = pd.DataFrame({"Close": [100]}, index=pd.DatetimeIndex(["2026-08-13 09:00"], tz="Europe/Istanbul"))
        now = datetime(2026, 8, 14, 14, 20, tzinfo=ZoneInfo("Europe/Istanbul"))
        self.assertFalse(build_bar_state(data, "BIST", "1d", now)["is_live"])


if __name__ == "__main__":
    unittest.main()
