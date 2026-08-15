import unittest

import pandas as pd

from src.technical_commentary import build_technical_commentary


def data_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Close": 100.0,
                "PLUS_DI": 20.0,
                "MINUS_DI": 25.0,
                "RSI": 48.0,
                "RSI_MA": 50.0,
                "MACD": -1.0,
                "MACD_SIGNAL": -0.8,
                "MACD_HIST": -0.2,
                "SMI": -10.0,
                "SMI_EMA": -8.0,
                "STOCH_K": 30.0,
                "STOCH_D": 35.0,
                "BB_WIDTH": 4.0,
                "BB_WIDTH_RANK": 18.0,
                "ATR_RANK": 30.0,
                "OBV": 1_000.0,
            },
            {
                "Close": 100.2,
                "PLUS_DI": 28.0,
                "MINUS_DI": 20.0,
                "RSI": 52.0,
                "RSI_MA": 50.0,
                "MACD": -0.6,
                "MACD_SIGNAL": -0.7,
                "MACD_HIST": 0.1,
                "SMI": 5.0,
                "SMI_EMA": 2.0,
                "STOCH_K": 55.0,
                "STOCH_D": 45.0,
                "BB_WIDTH": 4.2,
                "BB_WIDTH_RANK": 19.0,
                "ATR_RANK": 35.0,
                "OBV": 1_100.0,
            },
        ]
    )


def context(structure: str = "HH / HL", regime: str = "Denge / sıkışma") -> dict:
    return {
        "regime": {"state": regime, "adx": 22.0, "adx_delta": 1.0},
        "structure": {"state": structure, "high": 110.0, "low": 95.0},
        "profile": {
            "position": "Value Area içinde",
            "developing_acceptance": "Developing profile kabulü oluşmadı",
            "poc": 101.0,
            "vah": 106.0,
            "val": 96.0,
            "poc_migration": "Yatay",
        },
        "anchored_vwaps": {"manual": 99.0},
        "relative_volume": 0.7,
        "ma_structure": {
            "groups": {
                "Çok kısa": {"above": 4, "total": 4},
                "Kısa": {"above": 5, "total": 5},
                "Orta": {"above": 3, "total": 3},
                "Uzun": {"above": 3, "total": 3},
            }
        },
        "divergences": {
            "indicators": {
                "RSI": {"detected": False},
                "MACD": {"detected": False},
                "SMI": {"detected": True, "state": "Pozitif gizli uyumsuzluk", "event_age": 2},
            }
        },
    }


def decision(rs_tone: str = "negative", mtf_tone: str = "warning") -> dict:
    return {
        "relative_strength": {"state": "Göreceli zayıflıyor", "benchmark": "XU100", "tone": rs_tone},
        "multi_timeframe": {"state": "Zaman dilimleri karışık", "tone": mtf_tone},
        "liquidity": {"state": "Yüksek TL likiditesi"},
    }


class TechnicalCommentaryTests(unittest.TestCase):
    def test_squeeze_does_not_claim_directional_breakout(self) -> None:
        result = build_technical_commentary(data_frame(), context(), decision(), {"is_live": False})
        self.assertIn("Denge / teyit bekliyor", result["stance"])
        self.assertIn("bant genişlemesi", result["headline"])
        self.assertTrue(any("Sıkışma tek başına yön vermez" in item for item in result["watch"]))

    def test_commentary_exposes_conflicts_and_active_hidden_divergence(self) -> None:
        result = build_technical_commentary(data_frame(), context(), decision(), {"is_live": True})
        self.assertTrue(any("benchmarka göre zayıflıyor" in item for item in result["conflicts"]))
        self.assertTrue(any("CANLI" in item for item in result["conflicts"]))
        self.assertTrue(any("Pozitif gizli uyumsuzluk" in item for item in result["evidence"]))

    def test_method_does_not_create_composite_signal_score(self) -> None:
        result = build_technical_commentary(data_frame(), context(), decision(), {"is_live": False})
        self.assertIn("birleşik AL/SAT puanı üretmez", result["method"])
        self.assertEqual(result["framework"][0], "Regime")
        self.assertEqual(result["framework"][-1], "Exit")
        self.assertEqual(len(result["visual_rows"]), 5)


if __name__ == "__main__":
    unittest.main()
