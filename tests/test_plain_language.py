import unittest

from src.plain_language import build_plain_summary

JARGON = [
    "RVOL", "ATR", "VAH", "VAL", "POC", "EMA", "MACD", "RSI", "ADX", "SMI",
    "Bollinger", "AVWAP", "divergence", "uyumsuzluk", "momentum", "percentile",
]


def summary(**overrides):
    payload = {
        "symbol": "THYAO",
        "price": 300.5,
        "change_pct": -0.17,
        "setup_context": {
            "setup": {"name": "Sıkışma / karar bölgesi", "bias": "iki yönlü"},
            "duration": {"squeeze_bars": 7},
            "participation_reading": {"rvol_1": 0.56},
        },
        "scenario": {"strengthen": ["325.50 üzerinde kapanış: yukarı çözülme", "295.25 altında kapanış: aşağı çözülme"]},
        "clarity": {"state": "Düşük"},
        "bar_state": {"is_live": False},
    }
    payload.update(overrides)
    return build_plain_summary(**payload)


class PlainLanguageTests(unittest.TestCase):
    def test_summary_avoids_technical_jargon(self) -> None:
        text = summary()["text"]
        for term in JARGON:
            self.assertNotIn(term.casefold(), text.casefold(), f"'{term}' sade özette geçmemeli")

    def test_summary_states_price_and_both_thresholds(self) -> None:
        text = summary()["text"]
        self.assertIn("300.50", text)
        self.assertIn("325.50", text)
        self.assertIn("295.25", text)
        self.assertIn("olursa yukarı", text)
        self.assertIn("olursa aşağı", text)

    def test_squeeze_duration_is_expressed_in_days(self) -> None:
        self.assertIn("7 işlem günüdür", summary()["text"])

    def test_low_volume_is_framed_as_expected_inside_squeeze(self) -> None:
        text = summary()["text"]
        self.assertIn("beklenen bir durum", text)

    def test_low_volume_is_a_warning_outside_squeeze(self) -> None:
        text = summary(
            setup_context={
                "setup": {"name": "Trend devamı", "bias": "aşağı"},
                "duration": {"squeeze_bars": 0},
                "participation_reading": {"rvol_1": 0.56},
            }
        )["text"]
        self.assertIn("katılım zayıf", text)
        self.assertNotIn("beklenen bir durum", text)

    def test_failed_breakdown_is_explained_in_everyday_words(self) -> None:
        text = summary(
            setup_context={
                "setup": {"name": "Destekte reddedilme / başarısız aşağı kırılım", "bias": "iki yönlü"},
                "duration": {"squeeze_bars": 0},
                "participation_reading": {"rvol_1": 1.0},
            }
        )["text"]
        self.assertIn("aşağı kırmayı denedi ama başaramadı", text)

    def test_live_bar_warning_is_added(self) -> None:
        text = summary(bar_state={"is_live": True})["text"]
        self.assertIn("henüz kapanmadı", text)

    def test_disclaimer_always_present(self) -> None:
        self.assertIn("tavsiyesi değildir", summary()["text"])

    def test_unknown_setup_falls_back_without_crashing(self) -> None:
        text = summary(
            setup_context={
                "setup": {"name": "Bilinmeyen kurulum", "bias": "iki yönlü"},
                "duration": {},
                "participation_reading": {},
            }
        )["text"]
        self.assertIn("klasik bir kalıba tam oturmuyor", text)


if __name__ == "__main__":
    unittest.main()
