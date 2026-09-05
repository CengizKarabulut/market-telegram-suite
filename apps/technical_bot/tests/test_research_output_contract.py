from pathlib import Path
from types import SimpleNamespace

from src import fundamental_card, moving_average_card, research_card, research_chart
from src import research_telegram as telegram
from src.research_commentary_rich import _technical_paragraph_rich
from src.research_theme import apply_white_theme


def test_white_theme_keeps_pine_indicator_colours() -> None:
    original_pine_blue = research_chart.PINE_BLUE
    original_rsi_purple = research_chart.RSI_PURPLE

    apply_white_theme()

    assert fundamental_card.BG == "#FFFFFF"
    assert moving_average_card.BG == "#FFFFFF"
    assert research_card.BG == "#FFFFFF"
    assert research_chart.BG == "#FFFFFF"
    assert research_chart.PANEL == "#FFFFFF"
    assert research_chart.TEXT != "#FFFFFF"
    assert research_chart.PINE_BLUE == original_pine_blue
    assert research_chart.RSI_PURPLE == original_rsi_purple


def test_rich_technical_commentary_contains_full_evidence_stack() -> None:
    report = SimpleNamespace(
        technical={
            "score": 62.0,
            "label": "KARIŞIK",
            "structure": {"state": "HH / HL", "event": "BOS YUKARI"},
            "weekly_structure": {"state": "HH / HL", "event": "YENİ KIRILIM YOK"},
            "monthly_structure": {"state": "LH / HL", "event": "VERİ YETERSİZ"},
            "alpha_trend_state": "FİYAT ÜSTÜNDE / YÜKSELEN",
            "bollinger_state": "ORTA BAND ÜSTÜ",
            "rsi14": 58.4,
            "latest_rsi_divergence": {"kind": "Regular Bullish"},
            "smi": 44.0,
            "smi_signal": 39.0,
            "macd_hist": 0.125,
            "obv_10d_change": 7.2,
            "rvol20": 1.65,
            "atr_pct": 3.4,
            "elliott": {
                "primary": "YÜKSELİŞ İTKİ / DÜZELTME ADAYI",
                "alternate": "ABC DÜZELTMESİ",
                "confidence": 65,
                "invalidation": 42.25,
            },
        }
    )

    text = _technical_paragraph_rich(report)

    for term in (
        "Günlük",
        "haftalık",
        "aylık",
        "BOS YUKARI",
        "AlphaTrend",
        "Bollinger",
        "RSI",
        "Regular Bullish",
        "SMI",
        "MACD",
        "OBV",
        "RVOL20",
        "ATR",
        "Elliott",
        "invalidation",
    ):
        assert term in text


def test_research_bundle_sends_four_visuals_before_commentary(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(telegram, "_destination", lambda: ("token", "chat", "thread"))
    monkeypatch.setattr(telegram, "_caption", lambda report: "summary caption")
    monkeypatch.setattr(telegram, "commentary_messages", lambda report: ("yorum-1", "yorum-2"))

    def fake_photo(token, chat_id, thread_id, image_path, caption=""):
        calls.append(("photo", Path(image_path).name))
        return {"result": {"message_id": len(calls), "photo": [{}]}}

    def fake_text(token, chat_id, thread_id, text):
        calls.append(("text", text))
        return {"result": {"message_id": len(calls), "text": text}}

    monkeypatch.setattr(telegram, "_send_photo", fake_photo)
    monkeypatch.setattr(telegram, "_send_text", fake_text)

    paths = [tmp_path / name for name in ("ozet.png", "temel.png", "ma.png", "teknik.png")]
    report = SimpleNamespace(symbol="TEST")
    results = telegram.send_research_bundle(*paths, report)

    assert [kind for kind, _ in calls] == ["photo", "photo", "photo", "photo", "text", "text"]
    assert [name for kind, name in calls if kind == "photo"] == [
        "ozet.png",
        "temel.png",
        "ma.png",
        "teknik.png",
    ]
    assert len(results) == 6
