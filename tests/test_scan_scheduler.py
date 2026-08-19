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
    save_state,
)


def moment(day: int, hour: int, minute: int) -> datetime:
    # 2026-08-17 Pazartesi, 2026-08-22 Cumartesi
    return datetime(2026, 8, day, hour, minute, tzinfo=MARKET_TIMEZONE)


class SlotSelectionTests(unittest.TestCase):
    def test_slot_fires_once_its_time_has_passed(self) -> None:
        slot = due_slot(moment(17, 10, 31), {})
        self.assertIsNotNone(slot)
        self.assertEqual(slot.key, "10:30")
        self.assertEqual(slot.intervals, "1h,4h")

    def test_slot_does_not_fire_early(self) -> None:
        self.assertIsNone(due_slot(moment(17, 10, 29), {}))

    def test_already_run_slot_is_skipped(self) -> None:
        state = {"10:30": "2026-08-17"}
        slot = due_slot(moment(17, 12, 31), state)
        self.assertEqual(slot.key, "12:30")

    def test_stale_slot_is_skipped_after_grace(self) -> None:
        """Uzun kesintiden sonra geçmiş slotların hepsi arka arkaya çalışmamalı."""
        self.assertIsNone(due_slot(moment(17, 13, 30), {}))

    def test_close_slot_uses_slow_intervals(self) -> None:
        state = {slot.key: "2026-08-17" for slot in SLOTS if slot.hour < 19}
        slot = due_slot(moment(17, 19, 35), state)
        self.assertEqual(slot.intervals, "1d,1wk,1mo")

    def test_weekend_never_fires(self) -> None:
        self.assertIsNone(due_slot(moment(22, 12, 31), {}))

    def test_new_day_resets_slots(self) -> None:
        state = {"10:30": "2026-08-17"}
        slot = due_slot(moment(18, 10, 31), state)
        self.assertEqual(slot.key, "10:30")


class StateTests(unittest.TestCase):
    def test_state_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            save_state({"10:30": "2026-08-17"}, path)
            self.assertEqual(load_state(path), {"10:30": "2026-08-17"})

    def test_missing_file_is_empty(self) -> None:
        self.assertEqual(load_state(Path("/tmp/olmayan_plan.json")), {})

    def test_corrupt_file_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            path.write_text("bozuk", encoding="utf-8")
            self.assertEqual(load_state(path), {})

    def test_mark_done_records_the_date(self) -> None:
        state = mark_done(SLOTS[0], moment(17, 10, 31), {})
        self.assertEqual(state["10:30"], "2026-08-17")

    def test_saved_state_is_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            save_state({"a": "b"}, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": "b"})
