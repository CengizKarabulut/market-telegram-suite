import unittest
import os
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np
from src.technical_commentary import build_technical_commentary
from src.stock_dashboard import render_report

class TestRenderRegression(unittest.TestCase):
    def test_render_v2_commentary_produces_valid_png(self):
        dates = pd.date_range("2026-01-01", periods=300)
        data = pd.DataFrame({
            "Open": np.random.uniform(100, 110, 300),
            "High": np.random.uniform(110, 120, 300),
            "Low": np.random.uniform(90, 100, 300),
            "Close": np.random.uniform(100, 110, 300),
            "Volume": np.random.uniform(100000, 1000000, 300),
            "RSI": np.random.uniform(30, 70, 300),
            "RSI_MA": np.random.uniform(45, 55, 300),
            "MACD": np.random.uniform(-1, 1, 300),
            "MACD_SIGNAL": np.random.uniform(-1, 1, 300),
            "MACD_HIST": np.random.uniform(-1, 1, 300),
            "SMI": np.random.uniform(-100, 100, 300),
            "SMI_EMA": np.random.uniform(-100, 100, 300),
            "STOCH_K": np.random.uniform(0, 100, 300),
            "STOCH_D": np.random.uniform(0, 100, 300),
            "ATR": np.random.uniform(1, 5, 300),
            "OBV": np.cumsum(np.random.uniform(-100, 100, 300)),
            "BB_UPPER": np.random.uniform(120, 130, 300),
            "BB_MID": np.random.uniform(110, 120, 300),
            "BB_LOWER": np.random.uniform(90, 100, 300),
            "SUPERTREND": np.random.uniform(90, 100, 300),
        }, index=dates)
        for p in [21, 50, 200]:
            data[f"EMA_{p}"] = data["Close"].ewm(span=p).mean()

        ctx = {
            "regime": {"state": "Denge", "adx": 22.0, "adx_delta": 0.5, "tone": "warning", "candidate": "Denge"},
            "structure": {"state": "HH / HL", "high": 120.0, "low": 90.0, "tone": "positive"},
            "profile": {"position": "Value Area i?inde", "developing_acceptance": "Kabul yok", "poc": 102.0, "vah": 108.0, "val": 98.0, "poc_migration": "Yatay", "tone": "neutral"},
            "semantic": {
                "trend_quality": {"state": "Bullish", "tone": "positive", "spread_state": "geni?liyor", "summary": "Trend pozitif"},
                "momentum_character": {"state": "Pozitif", "tone": "positive", "summary": "Momentum g??l?", "macd": {"histogram_character": "geni?liyor"}, "active_divergences": []},
                "participation": {"state": "Normal", "tone": "neutral", "rvol_1": 1.1, "summary": "Kat?l?m normal"},
                "price_action": {"state": "G??l?", "tone": "positive", "patterns": [], "summary": "Fiyat g??l?"},
                "level_confluence": {"summary": "Seviye uyumu var", "nearest_support": None, "nearest_resistance": None, "clusters": []}
            },
            "events": []
        }
        decision = {
            "relative_strength": {"available": True, "state": "Strong", "benchmark": "XU100", "tone": "positive", "ratio_slope_5_pct": 1.2, "periods": {"20": {"stock_return_pct": 1.0, "benchmark_return_pct": 0.5, "excess_return_pct": 0.5}}},
            "multi_timeframe": {"state": "Aligned", "tone": "positive", "frames": [{"label": "D", "state": "Up"}]},
            "liquidity": {"state": "High", "average_turnover_20": 1000000, "free_float_pct": 50.0, "warnings": []},
        }
        comm = build_technical_commentary(data, ctx, decision, {"is_live": False})
        status = {
            "symbol": "TEST", "price": 105.0, "change_pct": 1.2, "timestamp": "2026-08-16",
            "interval": "1D", "bar_state": {"label": "CLOSED", "is_live": False},
            "data_provider": "Mock", "download_period": "2y",
            "technical_commentary": comm,
            "decision_rows": [["Relative Strength", "Strong", "Positive", "positive"]],
            "ma": [{"period": 21, "sma": 104.0, "ema": 104.5, "sma_color": "green", "ema_color": "green"}],
            "momentum": [["RSI", "65", "Bullish", "positive"]],
            "trend_volatility_volume": [["Trend", "Up", "Strong", "positive"]],
            "location": [["Price", "Above POC", "Bullish", "positive"]],
            "participation": [["RVOL", "1.2x", "Normal", "neutral"]],
            "events": [["Breakout", "2026-08-15", "Bullish", "positive"]],
            "equality_tolerance_pct": 0.02,
            "executive": [
                ["Rejim", "Denge", "ADX 20", "warning"],
                ["Yap?", "Up", "Summary", "positive"],
                ["Momentum", "Bullish", "Summary", "positive"],
                ["Kat?l?m", "Normal", "Summary", "neutral"],
                ["Konum", "Inside VA", "Summary", "neutral"],
                ["Relative Strength", "Strong", "Summary", "positive"],
                ["Price Action", "Strong", "Summary", "positive"],
            ]
        }
        temp_file = Path(tempfile.gettempdir()) / "test_render_regression.png"
        try:
            render_report(data, status, temp_file)
            self.assertTrue(temp_file.exists(), "PNG file should be created")
            self.assertTrue(temp_file.stat().st_size > 0, "PNG file size should be greater than 0")
        finally:
            if temp_file.exists():
                temp_file.unlink()

if __name__ == "__main__":
    unittest.main()
