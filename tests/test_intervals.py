import unittest

import pandas as pd

from src.intervals import (
    INTERVALS,
    key_ema_periods,
    minimum_bars,
    resample,
    resolve,
    usable_ma_periods,
)

MA_PERIODS = [5, 8, 10, 13, 20, 21, 34, 50, 55, 89, 100, 144, 200, 233, 377]


def hourly_session(days: int = 2, hours: int = 8) -> pd.DataFrame:
    stamps = []
    for day in range(days):
        start = pd.Timestamp("2026-01-05 10:00") + pd.Timedelta(days=day)
        stamps.extend(start + pd.Timedelta(hours=hour) for hour in range(hours))
    index = pd.DatetimeIndex(stamps)
    size = len(index)
    return pd.DataFrame(
        {
            "Open": range(size),
            "High": range(1, size + 1),
            "Low": range(-1, size - 1),
            "Close": range(size),
            "Volume": [100.0] * size,
        },
        index=index,
    )


class IntervalResolutionTests(unittest.TestCase):
    def test_all_requested_timeframes_are_available(self) -> None:
        for key in ("5m", "15m", "30m", "1h", "2h", "4h", "1d", "1wk", "1mo"):
            self.assertIn(key, INTERVALS)

    def test_aliases_are_accepted(self) -> None:
        self.assertEqual(resolve("60m").key, "1h")
        self.assertEqual(resolve("1w").key, "1wk")
        self.assertEqual(resolve(" 1D ").key, "1d")

    def test_unknown_interval_raises(self) -> None:
        with self.assertRaises(ValueError):
            resolve("7m")

    def test_two_and_four_hour_are_derived_from_hourly(self) -> None:
        self.assertEqual(resolve("2h").source_interval, "1h")
        self.assertEqual(resolve("4h").source_interval, "1h")
        self.assertIsNone(resolve("1h").resample_rule)


class ResampleTests(unittest.TestCase):
    def test_ohlcv_aggregation_is_correct(self) -> None:
        result = resample(hourly_session(days=1), resolve("2h"))
        first = result.iloc[0]
        self.assertEqual(first["Open"], 0)
        self.assertEqual(first["High"], 2)
        self.assertEqual(first["Low"], -1)
        self.assertEqual(first["Close"], 1)
        self.assertEqual(first["Volume"], 200)

    def test_intraday_bins_align_to_session_start(self) -> None:
        result = resample(hourly_session(days=2, hours=8), resolve("4h"))
        self.assertEqual(len(result), 4)
        self.assertEqual(result.index[0].hour, 10)
        self.assertEqual(result.index[1].hour, 14)

    def test_no_empty_overnight_bars_are_produced(self) -> None:
        result = resample(hourly_session(days=2, hours=8), resolve("2h"))
        self.assertFalse(result["Close"].isna().any())
        self.assertEqual(len(result), 8)

    def test_native_interval_is_returned_untouched(self) -> None:
        frame = hourly_session(days=1)
        self.assertIs(resample(frame, resolve("1h")), frame)

    def test_monthly_bins_are_labelled_at_month_start(self) -> None:
        index = pd.bdate_range("2025-01-01", periods=60)
        frame = pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0}, index=index)
        monthly = resample(frame, resolve("1mo"))
        self.assertTrue(all(stamp.day == 1 for stamp in monthly.index))

    def test_daily_to_weekly_reduces_bar_count(self) -> None:
        index = pd.bdate_range("2025-01-01", periods=60)
        frame = pd.DataFrame(
            {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0},
            index=index,
        )
        weekly = resample(frame, resolve("1wk"))
        self.assertLess(len(weekly), len(frame))
        # İlk hafta eksik başlar; tam bir haftada beş işlem günü toplanmalı.
        self.assertAlmostEqual(float(weekly["Volume"].iloc[1]), 10.0 * 5, places=6)
        self.assertEqual(weekly.index[1].dayofweek, 0)


class AdaptivePeriodTests(unittest.TestCase):
    def test_long_periods_are_dropped_when_history_is_short(self) -> None:
        periods = usable_ma_periods(70, MA_PERIODS)
        self.assertNotIn(377, periods)
        self.assertNotIn(200, periods)
        self.assertIn(55, periods)

    def test_full_set_is_kept_when_history_is_long(self) -> None:
        self.assertEqual(usable_ma_periods(1000, MA_PERIODS), MA_PERIODS)

    def test_minimum_set_is_returned_for_very_short_history(self) -> None:
        self.assertEqual(len(usable_ma_periods(10, MA_PERIODS)), 6)

    def test_key_emas_fall_back_when_preferred_missing(self) -> None:
        self.assertEqual(key_ema_periods(MA_PERIODS), (21, 55, 233))
        fallback = key_ema_periods([5, 8, 10, 13, 20, 21, 34])
        self.assertEqual(len(fallback), 3)
        self.assertNotIn(233, fallback)

    def test_weekly_and_monthly_have_relaxed_bar_requirement(self) -> None:
        self.assertLess(minimum_bars(resolve("1mo"), MA_PERIODS), minimum_bars(resolve("1d"), MA_PERIODS))


if __name__ == "__main__":
    unittest.main()
