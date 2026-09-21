import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.scan_scheduler import (
    MARKET_TIMEZONE,
    SLOTS,
    due_slot,
    load_state,
    mark_done,
    resolve_intervals,
    save_state,
)


def moment(day: int, hour: int, minute: int) -> datetime:
    # 2026-08-17 Pazartesi, 2026-08-22 Cumartesi
    return datetime(2026, 8, day, hour, minute, tzinfo=MARKET_TIMEZONE)


EXPECTED_SLOTS = (
    (10, 20, "1h"),
    (10, 30, "1wk"),
    (10, 45, "1d"),
    (11, 0, "4h"),
    (11, 20, "1h"),
    (12, 20, "1h"),
    (12, 45, "1d"),
    (13, 0, "4h"),
    (13, 20, "1h"),
    (13, 45, "1wk"),
    (14, 20, "1h"),
    (14, 30, "4h"),
    (14, 45, "1d"),
    (15, 20, "1h"),
    (16, 0, "1wk"),
    (16, 20, "1h"),
    (16, 30, "4h"),
    (16, 45, "1d"),
    (17, 20, "1h"),
    (17, 25, "1wk"),
    (17, 30, "4h"),
    (17, 40, "1h"),
    (17, 45, "1d"),
    (18, 20, "1h"),
    (18, 30, "4h"),
    (18, 45, "1d"),
    (19, 0, "1wk"),
)


class SlotSelectionTests(unittest.TestCase):
    def test_schedule_matches_requested_market_clock(self) -> None:
        self.assertEqual(
            tuple((slot.hour, slot.minute, slot.intervals) for slot in SLOTS),
            EXPECTED_SLOTS,
        )

    def test_first_slot_fires_once_its_time_has_passed(self) -> None:
        slot = due_slot(moment(17, 10, 20), {})
        self.assertIsNotNone(slot)
        self.assertEqual(slot.key, "10:20")
        self.assertEqual(slot.intervals, "1h")

    def test_slot_does_not_fire_early(self) -> None:
        self.assertIsNone(due_slot(moment(17, 10, 19), {}))

    def test_already_run_slot_is_skipped(self) -> None:
        state = {"10:20": "2026-08-17"}
        slot = due_slot(moment(17, 10, 30), state)
        self.assertEqual(slot.key, "10:30")
        self.assertEqual(slot.intervals, "1wk")

    def test_stale_slot_is_skipped_after_grace(self) -> None:
        # 10:20 is stale at 11:06; 10:30 is still inside the 45 minute grace.
        slot = due_slot(moment(17, 11, 6), {})
        self.assertEqual(slot.key, "10:30")

    def test_each_core_timeframe_has_automatic_slots(self) -> None:
        self.assertEqual({slot.intervals for slot in SLOTS}, {"1h", "4h", "1d", "1wk"})

    def test_weekend_never_fires(self) -> None:
        self.assertIsNone(due_slot(moment(22, 12, 20), {}))

    def test_new_day_resets_slots(self) -> None:
        state = {"10:20": "2026-08-17"}
        slot = due_slot(moment(18, 10, 20), state)
        self.assertEqual(slot.key, "10:20")


class StateTests(unittest.TestCase):
    def test_state_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            save_state({"10:20": "2026-08-17"}, path)
            self.assertEqual(load_state(path), {"10:20": "2026-08-17"})

    def test_missing_file_is_empty(self) -> None:
        self.assertEqual(load_state(Path("/tmp/olmayan_plan.json")), {})

    def test_corrupt_file_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            path.write_text("bozuk", encoding="utf-8")
            self.assertEqual(load_state(path), {})

    def test_mark_done_records_the_date(self) -> None:
        state = mark_done(SLOTS[0], moment(17, 10, 20), {})
        self.assertEqual(state["10:20"], "2026-08-17")

    def test_saved_state_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            save_state({"a": "b"}, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": "b"})


class IntervalResolutionTests(unittest.TestCase):
    def test_auto_uses_fast_intervals_during_the_session(self) -> None:
        for hour in (10, 12, 14, 17):
            self.assertEqual(resolve_intervals("auto", moment(17, hour, 30)), "1h,4h")

    def test_auto_uses_daily_weekly_after_the_close(self) -> None:
        self.assertEqual(resolve_intervals("auto", moment(17, 19, 30)), "1d,1wk")
        self.assertEqual(resolve_intervals("auto", moment(17, 22, 0)), "1d,1wk")

    def test_explicit_value_is_respected(self) -> None:
        self.assertEqual(resolve_intervals("1h,1d", moment(17, 11, 0)), "1h,1d")

    def test_supported_aliases_are_canonicalized(self) -> None:
        self.assertEqual(resolve_intervals("60m,1w", moment(17, 11, 0)), "1h,1wk")

    def test_retired_intervals_are_rejected(self) -> None:
        for value in ("5m", "15m", "30m", "2h", "1mo"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_intervals(value, moment(17, 11, 0))

    def test_empty_value_uses_intraday_core(self) -> None:
        self.assertEqual(resolve_intervals("", moment(17, 11, 0)), "1h,4h")
        self.assertEqual(resolve_intervals(None, moment(17, 11, 0)), "1h,4h")

    def test_case_insensitive_auto(self) -> None:
        self.assertEqual(resolve_intervals("AUTO", moment(17, 11, 0)), "1h,4h")
