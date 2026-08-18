import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.screener import (
    SCREENS,
    basic_metrics,
    default_options,
    passes_liquidity,
    rank_key,
    run_screen,
    screen_symbol,
)
from src.screener_cli import summary_text
from src.stock_dashboard import calculate_indicators
from src.universe import Universe, load_universe, read_file


def frame(seed: int = 1, bars: int = 520, volatility: float = 0.016, spike: float = 1.0, volume_level: float = 17.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, volatility, bars)))
    volume = rng.lognormal(volume_level, 0.3, bars)
    volume[-1] *= spike
    return pd.DataFrame(
        {"Open": close, "High": close * 1.008, "Low": close * 0.992, "Close": close, "Volume": volume},
        index=pd.bdate_range("2024-01-01", periods=bars),
    )


class MetricsTests(unittest.TestCase):
    def test_basic_metrics_include_cheap_price_action_flags(self) -> None:
        metrics = basic_metrics(calculate_indicators(frame()))
        for key in ("pierced_down", "pierced_up", "stacked", "rvol", "bb_rank", "turnover"):
            self.assertIn(key, metrics)

    def test_pierced_down_detects_recovered_break(self) -> None:
        data = frame(seed=3)
        prior_low = float(data["Low"].iloc[-21:-1].min())
        data.iloc[-1, data.columns.get_loc("Low")] = prior_low * 0.97
        data.iloc[-1, data.columns.get_loc("Close")] = prior_low * 1.01
        metrics = basic_metrics(calculate_indicators(data))
        self.assertTrue(metrics["pierced_down"])

    def test_illiquid_symbol_is_filtered_out(self) -> None:
        options = default_options()
        thin = {"turnover": 1_000.0, "close": 5.0}
        self.assertFalse(passes_liquidity(thin, options))
        self.assertTrue(passes_liquidity({"turnover": 50_000_000.0, "close": 12.0}, options))

    def test_penny_stock_is_filtered_out(self) -> None:
        options = default_options()
        self.assertFalse(passes_liquidity({"turnover": 90_000_000.0, "close": 0.4}, options))


class ScreenTests(unittest.TestCase):
    def test_volume_spike_screen_matches(self) -> None:
        result = screen_symbol("TEST", frame(seed=5, spike=8.0), default_options(), ["hacim_patlamasi"])
        self.assertIsNotNone(result)
        self.assertIn("hacim_patlamasi", result.screens)

    def test_no_match_returns_none(self) -> None:
        self.assertIsNone(screen_symbol("TEST", frame(seed=5), default_options(), ["hacim_patlamasi"]))

    def test_deep_screen_populates_setup_name(self) -> None:
        matched = None
        for seed in range(30):
            result = screen_symbol("TEST", frame(seed=seed, volatility=0.004), default_options(), ["karar_bolgesi"])
            if result:
                matched = result
                break
        self.assertIsNotNone(matched, "sıkışma senaryosunda en az bir eşleşme beklenir")
        self.assertTrue(matched.setup)
        self.assertIn("karar_bolgesi", matched.screens)

    def test_unknown_screen_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            run_screen(["A"], lambda batch: {}, enabled=["olmayan_tarama"])

    def test_ranking_prefers_more_screens_then_volume(self) -> None:
        from src.screener import ScreenResult

        many = ScreenResult("A", 10, 1e8, 10, 1.2, 2, 50, screens=["a", "b"])
        loud = ScreenResult("B", 10, 1e8, 10, 5.0, 2, 50, screens=["a"])
        self.assertLess(rank_key(many), rank_key(loud))


class RobustnessTests(unittest.TestCase):
    def test_single_symbol_failure_does_not_stop_the_scan(self) -> None:
        good = frame(seed=2, spike=8.0)
        store = {"OK": good, "BOZUK": pd.DataFrame({"Close": [1.0]})}
        payload = run_screen(["OK", "BOZUK"], lambda batch: {t: store[t] for t in batch}, enabled=["hacim_patlamasi"])
        self.assertEqual(payload["matched"], 1)
        self.assertIn("BOZUK", payload["errors"])

    def test_batch_download_failure_is_recorded_per_symbol(self) -> None:
        def failing(batch):
            raise ConnectionError("ağ hatası")

        payload = run_screen(["A", "B"], failing)
        self.assertEqual(payload["processed"], 0)
        self.assertEqual(set(payload["errors"]), {"A", "B"})

    def test_missing_data_is_reported_not_silently_skipped(self) -> None:
        payload = run_screen(["YOK"], lambda batch: {})
        self.assertEqual(payload["errors"]["YOK"], "veri yok")


class SummaryTests(unittest.TestCase):
    def test_summary_is_produced_even_with_zero_matches(self) -> None:
        payload = {"requested": 600, "processed": 590, "matched": 0, "filtered_out": 120, "errors": {}, "results": []}
        text = summary_text(payload, "borsapy", 300.0)
        self.assertIn("600 sembol", text)
        self.assertIn("koşulları karşılayan sembol bulunamadı", text)

    def test_summary_lists_errors(self) -> None:
        payload = {"requested": 10, "processed": 7, "matched": 0, "filtered_out": 0, "errors": {"AAA": "x", "BBB": "y"}, "results": []}
        text = summary_text(payload, "borsapy", 10.0)
        self.assertIn("Hata veren semboller", text)
        self.assertIn("AAA", text)

    def test_summary_caps_long_result_lists(self) -> None:
        results = [
            {"ticker": f"T{index}", "close": 10.0, "rvol": 2.0, "bb_width_percentile": 10.0, "screens": ["hacim_patlamasi"], "setup": ""}
            for index in range(60)
        ]
        payload = {"requested": 600, "processed": 600, "matched": 60, "filtered_out": 0, "errors": {}, "results": results}
        text = summary_text(payload, "borsapy", 100.0)
        self.assertIn("sembol daha", text)
        self.assertNotIn("T59", text)


class UniverseTests(unittest.TestCase):
    def test_file_source_reads_and_cleans_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.txt"
            path.write_text("# yorum\nTHYAO\nasels\nTHYAO\nXU100\nAB\n", encoding="utf-8")
            universe = read_file(path)
            self.assertEqual(universe.symbols, ["ASELS", "THYAO"])

    def test_cache_is_used_when_fresh(self) -> None:
        import time

        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text(json.dumps({"symbols": ["AAA", "BBB"], "source": "borsapy", "fetched_at": time.time()}), encoding="utf-8")
            universe = load_universe("auto", None, cache_path=cache)
            self.assertEqual(universe.symbols, ["AAA", "BBB"])
            self.assertIn("önbellek", universe.source)

    def test_stale_cache_is_ignored_and_falls_back_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text(json.dumps({"symbols": ["ESKI"], "source": "borsapy", "fetched_at": 0}), encoding="utf-8")
            watchlist = Path(directory) / "list.txt"
            watchlist.write_text("THYAO\nASELS\n", encoding="utf-8")
            universe = load_universe("auto", watchlist, cache_path=cache)
            self.assertNotIn("ESKI", universe.symbols)

    def test_universe_size_property(self) -> None:
        self.assertEqual(Universe(["A", "B"], "test", 0.0).size, 2)


class ScreenCatalogueTests(unittest.TestCase):
    def test_every_screen_has_label_and_description(self) -> None:
        for name, screen in SCREENS.items():
            self.assertTrue(screen["label"], name)
            self.assertTrue(screen["description"], name)
            self.assertTrue(callable(screen["cheap"]), name)

    def test_deep_screens_have_a_cheap_prefilter(self) -> None:
        """Pahalı taramalar ucuz ön koşul olmadan tüm evreni yavaşlatır."""
        # Nötr piyasa: bantlar orta genişlikte, RSI 50, yönlülük zayıf, kırılım yok.
        metrics = {
            "bb_rank": 50.0, "rvol": 1.0, "rsi": 50.0, "adx": 15.0, "atr_pct": 2.0,
            "close": 10.0, "turnover": 1e8, "macd_hist": 0.0, "volume": 1e6,
            "pierced_down": False, "pierced_up": False, "stacked": False,
        }
        options = default_options()
        for name, screen in SCREENS.items():
            if screen["deep"]:
                self.assertFalse(screen["cheap"](metrics, options), f"{name} nötr ölçütlerde derin aşamayı tetiklememeli")


if __name__ == "__main__":
    unittest.main()
