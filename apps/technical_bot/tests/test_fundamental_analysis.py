from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd

import src.bot_runner_fundamental as bot_runner_fundamental
import src.fundamental_analysis as fundamental_analysis
import src.fundamental_card as fundamental_card


PERIODS = ["2026/06", "2026/03", "2025/12", "2025/09", "2025/06", "2025/03", "2024/12", "2024/09"]


def frame(rows: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=PERIODS).T


class FakeTicker:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.fast_info = {"last_price": 191.4, "pe_ratio": 6.2}
        self.info = {
            "longName": "Garanti Bankası",
            "sector": "Banking",
            "priceToBook": 1.35,
            "trailingPE": 6.2,
        }

    def get_balance_sheet(self, **_: object) -> pd.DataFrame:
        return frame(
            {
                "Toplam Varlıklar": [3000, 2850, 2700, 2550, 2400, 2250, 2100, 1950],
                "Özkaynaklar": [330, 315, 300, 285, 270, 255, 240, 225],
                "Krediler": [1800, 1710, 1620, 1530, 1440, 1360, 1280, 1200],
                "Mevduat": [2000, 1900, 1800, 1710, 1620, 1530, 1440, 1360],
            }
        )

    def get_income_stmt(self, **_: object) -> pd.DataFrame:
        return frame(
            {
                "Net Faiz Geliri": [70, 66, 63, 60, 52, 50, 48, 46],
                "Faiz Gelirleri": [130, 124, 118, 112, 100, 96, 92, 88],
                "Faiz Giderleri": [-60, -58, -55, -52, -48, -46, -44, -42],
                "Faaliyet Giderleri": [-28, -27, -26, -25, -23, -22, -21, -20],
                "Net Dönem Karı": [32, 30, 29, 28, 24, 23, 22, 21],
            }
        )


class FundamentalAnalysisTests(unittest.TestCase):
    def test_profile_classification(self) -> None:
        self.assertEqual(fundamental_analysis._classify("GARAN", "Financial Services"), "BANK")
        self.assertEqual(fundamental_analysis._classify("ZGYO", ""), "GYO")
        self.assertEqual(fundamental_analysis._classify("THYAO", "Airlines"), "GENERIC")

    def test_provider_sentinel_is_missing(self) -> None:
        self.assertIsNone(fundamental_analysis._clean_multiple(-100.0))
        self.assertEqual(fundamental_analysis._clean_multiple(7.5), 7.5)

    def test_garan_builds_bank_specific_factors(self) -> None:
        fake_module = types.SimpleNamespace(Ticker=FakeTicker)
        original = sys.modules.get("borsapy")
        sys.modules["borsapy"] = fake_module
        try:
            report = fundamental_analysis.build_fundamental_report("GARAN")
        finally:
            if original is None:
                sys.modules.pop("borsapy", None)
            else:
                sys.modules["borsapy"] = original
        self.assertEqual(report.profile, "BANK")
        self.assertEqual(report.symbol, "GARAN")
        self.assertEqual(
            [factor.name for factor in report.factors],
            ["Gelir / Gider Yapısı", "Büyüme", "Kârlılık", "Sermaye Gücü", "Bilanço Yapısı"],
        )
        self.assertIsNotNone(report.overall_score)
        self.assertGreater(report.coverage, 0.7)
        self.assertIn("resmi SYR değildir", report.note)

    def test_mobile_card_renders_png(self) -> None:
        report = fundamental_analysis.FundamentalReport(
            symbol="GARAN",
            company_name="Garanti Bankası",
            price=191.4,
            sector="Banking",
            profile="BANK",
            overall_score=3.42,
            coverage=0.88,
            factors=(
                fundamental_analysis.Factor("Gelir / Gider Yapısı", 4.5, 1.0, "Net faiz %+24.0"),
                fundamental_analysis.Factor("Büyüme", 2.4, 1.0, "Kredi %+18.0"),
                fundamental_analysis.Factor("Kârlılık", 3.8, 1.0, "ROE %+28.0"),
                fundamental_analysis.Factor("Sermaye Gücü", 3.1, 0.8, "Özk./aktif %+11.0"),
                fundamental_analysis.Factor("Bilanço Yapısı", 3.3, 1.0, "Kredi/mevduat 0.90x"),
            ),
            positives=("Kârlılık: güçlü görünüm (3.8/5).",),
            risks=("Büyüme: izlenmeli (2.4/5).",),
            metrics={},
            note="Sermaye Gücü resmi SYR değildir.",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = fundamental_card.render_fundamental_card(report, Path(directory) / "garanti.png")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 10_000)

    def test_temel_command_ticker_validation(self) -> None:
        self.assertEqual(bot_runner_fundamental._validate_ticker(["garan"]), ("GARAN", None))
        ticker, error = bot_runner_fundamental._validate_ticker([])
        self.assertIsNone(ticker)
        self.assertIn("Sembol belirtilmedi", str(error))
        ticker, error = bot_runner_fundamental._validate_ticker(["GARAN", "4h"])
        self.assertIsNone(ticker)
        self.assertIn("zaman diliminden bağımsız", str(error))


if __name__ == "__main__":
    unittest.main()
