import tempfile
import unittest
from pathlib import Path

from src.analyst_card import _blocks, render_analyst_card, render_analyst_cards

STATUS = {
    "symbol": "THYAO",
    "price": 300.5,
    "change_pct": -0.17,
    "timestamp": "2026-08-18T09:00:00+03:00",
    "data_provider": "borsapy/TradingView",
    "bar_state": {"label": "TEYİTLİ", "is_live": False},
    "technical_commentary": {
        "setup": {"name": "Sıkışma / karar bölgesi", "bias": "iki yönlü", "tone": "neutral", "description": "Dar aralıkta denge."},
        "duration": {"summary": "7 bardır dar bant bölgesinde"},
        "analyst_note": "Birinci paragraf.\n\nİkinci paragraf.",
        "reconciliation": "Kanıtlar iki yöne dağılmış.",
        "plain_summary": {"text": "THYAO 300,50 seviyesinde. Fiyat dar bir aralıkta."},
        "supporting_evidence": [{"family": "Yapı", "state": "HH / HL"}],
        "counter_evidence": [{"family": "Momentum", "state": "Negatif"}],
        "clarity": {"state": "Düşük", "tone": "warning", "reason": "Kanıtlar dağılmış."},
        "levels": {"clusters": [{"low": 297.56, "high": 299.5, "side": "destek", "strength": "Orta", "members": ["BB Alt", "VAL"]}]},
        "scenario_map": {
            "strengthen": ["325.50 üzerinde kapanış: yukarı çözülme", "295.25 altında kapanış: aşağı çözülme"],
            "weaken": ["Aralık içinde kalınması"],
            "neutral": ["Sıkışmanın sürmesi"],
            "labels": {"strengthen": "Yukarı/aşağı çözülme koşulları", "weaken": "Kurulumu geçersiz kılacak", "neutral": "Durumu koruyacak"},
        },
        "changes": ["Yeni olay: SMI ↓ -40."],
    },
}


class AnalystCardTests(unittest.TestCase):
    def test_card_png_is_created_with_content_driven_height(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = render_analyst_card(STATUS, Path(directory) / "card.png")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 10_000)

    def test_longer_note_produces_taller_card(self) -> None:
        long_status = {**STATUS, "technical_commentary": {**STATUS["technical_commentary"]}}
        long_status["technical_commentary"]["analyst_note"] = "Uzun paragraf. " * 200
        with tempfile.TemporaryDirectory() as directory:
            short = render_analyst_card(STATUS, Path(directory) / "short.png")
            tall = render_analyst_card(long_status, Path(directory) / "tall.png")
            self.assertGreater(tall.stat().st_size, short.stat().st_size)

    def test_two_sided_thresholds_are_coloured_by_direction(self) -> None:
        blocks = _blocks(STATUS)
        upward = [block for block in blocks if "yukarı çözülme" in block.text]
        downward = [block for block in blocks if "aşağı çözülme" in block.text]
        self.assertTrue(upward and downward)
        self.assertNotEqual(upward[0].colour, downward[0].colour)

    def test_card_includes_plain_summary_and_setup(self) -> None:
        texts = " ".join(block.text for block in _blocks(STATUS))
        self.assertIn("SADE ÖZET", texts)
        self.assertIn("Sıkışma / karar bölgesi", texts)
        self.assertIn("Kanıtlar iki yöne dağılmış.", texts)

    def test_missing_sections_do_not_break_rendering(self) -> None:
        minimal = {"symbol": "X", "price": 1.0, "change_pct": 0.0, "technical_commentary": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = render_analyst_card(minimal, Path(directory) / "minimal.png")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()


class CardWrappingTests(unittest.TestCase):
    def test_bold_text_wraps_earlier_than_regular_text(self) -> None:
        from src.analyst_card import _wrap

        text = "Dirençte reddedilme / başarısız yukarı kırılım • eğilim: iki yönlü uzun başlık"
        regular = _wrap(text, 18, 9.0, "normal")
        bold = _wrap(text, 18, 9.0, "bold")
        self.assertGreaterEqual(len(bold), len(regular))

    def test_analyst_note_first_paragraph_is_not_duplicated(self) -> None:
        blocks = _blocks(STATUS)
        texts = [block.text for block in blocks]
        self.assertNotIn("Birinci paragraf.", texts)
        self.assertIn("İkinci paragraf.", texts)


class CardPagingTests(unittest.TestCase):
    def test_two_separate_cards_are_produced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = render_analyst_cards(STATUS, Path(directory))
            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 5_000)

    def test_each_card_is_shorter_than_the_combined_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            combined = render_analyst_card(STATUS, Path(directory) / "combined.png")
            paths = render_analyst_cards(STATUS, Path(directory))
            for path in paths:
                self.assertLess(path.stat().st_size, combined.stat().st_size)

    def test_bar_state_is_expressed_in_plain_words(self) -> None:
        from src.plain_language import bar_state_plain

        self.assertIn("Gün kapandı", bar_state_plain({"label": "TEYİTLİ", "is_live": False}))
        self.assertIn("Gün sürüyor", bar_state_plain({"label": "CANLI", "is_live": True}))


class CardBalanceTests(unittest.TestCase):
    def test_evidence_appears_only_on_the_first_card(self) -> None:
        from src.analyst_card import CARD_PAGES

        commentary = STATUS["technical_commentary"]
        overview = " ".join(block.text for block in CARD_PAGES[0][1](commentary))
        detail = " ".join(block.text for block in CARD_PAGES[1][1](commentary))
        self.assertIn("KANIT DENGESİ", overview)
        self.assertNotIn("KANIT DENGESİ", detail)

    def test_levels_and_scenarios_appear_on_the_second_card(self) -> None:
        from src.analyst_card import CARD_PAGES

        detail = " ".join(block.text for block in CARD_PAGES[1][1](STATUS["technical_commentary"]))
        self.assertIn("TEKNİK YOĞUNLAŞMA BÖLGELERİ", detail)
        self.assertIn("yukarı çözülme", detail)
