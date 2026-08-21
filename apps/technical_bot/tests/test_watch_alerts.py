import tempfile
import unittest
from pathlib import Path

from src.watch_alerts import (
    MAX_WATCHED,
    Watch,
    add_watch,
    check_break,
    describe,
    load_watches,
    remove_watch,
    save_watches,
)


def watch(ticker: str = "THYAO", upper: float = 310.0, lower: float = 290.0) -> Watch:
    return Watch(ticker=ticker, interval="1d", upper=upper, lower=lower, setup="Sıkışma / karar bölgesi", added_at="2026-08-20T10:00")


class BreakTests(unittest.TestCase):
    def test_close_above_upper_triggers(self) -> None:
        message = check_break(watch(), 312.0)
        self.assertIn("yukarı eşik aşıldı", message)
        self.assertIn("312", message)

    def test_close_below_lower_triggers(self) -> None:
        self.assertIn("aşağı eşik aşıldı", check_break(watch(), 288.0))

    def test_close_inside_range_is_silent(self) -> None:
        self.assertEqual(check_break(watch(), 300.0), "")

    def test_already_triggered_does_not_repeat(self) -> None:
        item = watch()
        item.triggered = "2026-08-20T11:00"
        self.assertEqual(check_break(item, 320.0), "")

    def test_alert_states_it_is_not_advice(self) -> None:
        self.assertIn("önerisi değildir", check_break(watch(), 312.0))


class ListTests(unittest.TestCase):
    def test_add_and_remove(self) -> None:
        watches, message = add_watch({}, watch())
        self.assertIn("THYAO", watches)
        self.assertIn("takibe alındı", message)
        watches, message = remove_watch(watches, "thyao")
        self.assertEqual(watches, {})
        self.assertIn("takipten çıkarıldı", message)

    def test_existing_symbol_is_updated_not_duplicated(self) -> None:
        watches, _ = add_watch({}, watch())
        watches, message = add_watch(watches, watch(upper=320.0))
        self.assertEqual(len(watches), 1)
        self.assertIn("güncellendi", message)

    def test_capacity_is_enforced(self) -> None:
        watches = {f"AAA{index:02d}": watch(f"AAA{index:02d}") for index in range(MAX_WATCHED)}
        updated, message = add_watch(watches, watch("YENIX"))
        self.assertIsNone(updated)
        self.assertIn("dolu", message)

    def test_removing_missing_symbol_is_reported(self) -> None:
        self.assertIsNone(remove_watch({}, "YOKXX")[0])

    def test_empty_description_guides_the_user(self) -> None:
        self.assertIn("/takip THYAO", describe({}))


class PersistenceTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watch.json"
            save_watches({"THYAO": watch()}, path)
            loaded = load_watches(path)
            self.assertEqual(loaded["THYAO"].upper, 310.0)

    def test_corrupt_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watch.json"
            path.write_text("bozuk", encoding="utf-8")
            self.assertEqual(load_watches(path), {})

    def test_malformed_entry_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "watch.json"
            path.write_text('{"AAA": {"ticker": "AAA"}}', encoding="utf-8")
            self.assertEqual(load_watches(path), {})
