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
    def test_only_core_timeframes_are_available(self) -> None:
        self.assertEqual(tuple(INTERVALS), ("1h", "4h", "1d", "1wk"))

    def test_aliases_are_accepted(self) -> None:
        self.assertEqual(resolve("60m").key, "1h")
        self.assertEqual(resolve("1w").key, "1wk")
        self.assertEqual(resolve(" 1D ").key, "1d")

    def test_retired_and_unknown_intervals_raise(self) -> None:
        for value in ("5m", "15m", "30m", "2h", "1mo", "7m"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    resolve(value)

    def test_four_hour_is_derived_from_hourly(self) -> None:
        self.assertEqual(resolve("4h").source_interval, "1h")
        self.assertIsNone(resolve("1h").resample_rule)


class ResampleTests(unittest.TestCase):
    def test_four_hour_ohlcv_aggregation_is_correct(self) -> None:
        result = resample(hourly_session(days=1), resolve("4h"))
        first = result.iloc[0]
        self.assertEqual(first["Open"], 0)
        self.assertEqual(first["High"], 4)
        self.assertEqual(first["Low"], -1)
        self.assertEqual(first["Close"], 3)
        self.assertEqual(first["Volume"], 400)

    def test_intraday_bins_align_to_session_start(self) -> None:
        result = resample(hourly_session(days=2, hours=8), resolve("4h"))
        self.assertEqual(len(result), 4)
        self.assertEqual(result.index[0].hour, 10)
        self.assertEqual(result.index[1].hour, 14)

    def test_closing_auction_bar_is_merged_not_left_as_stub(self) -> None:
        frame = hourly_session(days=2, hours=9)
        result = resample(frame, resolve("4h"))
        self.assertEqual(len(result), 4, "günde iki 4 saatlik mum beklenir")
        volumes = result["Volume"].tolist()
        self.assertNotIn(100.0, volumes, "tek barlık sahte mum üretilmemeli")
        self.assertEqual(volumes[1], 500.0)

    def test_every_source_bar_is_accounted_for(self) -> None:
        frame = hourly_session(days=3, hours=9)
        result = resample(frame, resolve("4h"))
        self.assertAlmostEqual(float(result["Volume"].sum()), float(frame["Volume"].sum()), places=6)

    def test_native_interval_is_returned_untouched(self) -> None:
        frame = hourly_session(days=1)
        self.assertIs(resample(frame, resolve("1h")), frame)

    def test_daily_to_weekly_reduces_bar_count(self) -> None:
        index = pd.bdate_range("2025-01-01", periods=60)
        frame = pd.DataFrame(
            {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 10.0},
            index=index,
        )
        weekly = resample(frame, resolve("1wk"))
        self.assertLess(len(weekly), len(frame))
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

    def test_key_emas_are_never_substituted(self) -> None:
        self.assertEqual(key_ema_periods(MA_PERIODS), (21, 55, 233))
        partial = key_ema_periods([5, 8, 10, 13, 20, 21, 34, 50, 55, 89, 100])
        self.assertEqual(partial, (21, 55))
        self.assertNotIn(100, partial)

    def test_missing_periods_are_listed(self) -> None:
        from src.intervals import missing_ma_periods

        self.assertEqual(missing_ma_periods(145, MA_PERIODS), [144, 200, 233, 377])
        self.assertEqual(missing_ma_periods(1000, MA_PERIODS), [])

    def test_minimum_bars_allows_recently_listed_symbols(self) -> None:
        for key in ("1h", "4h", "1d", "1wk"):
            self.assertEqual(minimum_bars(resolve(key), MA_PERIODS), 120)

    def test_short_history_still_yields_a_usable_period_set(self) -> None:
        periods = usable_ma_periods(145, MA_PERIODS)
        self.assertGreaterEqual(len(periods), 10)
        self.assertLessEqual(max(periods) + 5, 145)


class RankWindowTests(unittest.TestCase):
    def test_window_scales_with_supported_interval_length(self) -> None:
        from src.intervals import rank_window

        self.assertGreater(rank_window("1h"), rank_window("1d"))
        self.assertGreater(rank_window("1d"), rank_window("1wk"))

    def test_daily_window_stays_one_trading_year(self) -> None:
        from src.intervals import rank_window

        self.assertEqual(rank_window("1d"), 252)

    def test_hour_alias_uses_hour_window(self) -> None:
        from src.intervals import rank_window

        self.assertEqual(rank_window("60m"), rank_window("1h"))


if __name__ == "__main__":
    unittest.main()
