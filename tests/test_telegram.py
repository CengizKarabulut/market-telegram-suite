import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.analyst_card import render_analyst_cards  # noqa: F401
from src.send_telegram import send
from src.telegram_client import CAPTION_LIMIT, MESSAGE_LIMIT, split_message

STATUS = {
    "symbol": "THYAO",
    "price": 305.25,
    "change_pct": -0.89,
    "timestamp": "2026-08-14T09:00:00+03:00",
    "data_provider": "borsapy/TradingView",
    "market_context": {
        "regime": {"state": "Dengeli / sıkışan piyasa"},
        "structure": {"state": "LH / LL", "event": "Swing Low altı BOS"},
        "profile": {"position": "Value Area içinde", "poc": 326.62, "vah": 336.25, "val": 301.25},
        "relative_volume": 0.68,
        "divergences": {
            "indicators": {
                "RSI": {"detected": False, "state": "Son 5 barda aktif uyumsuzluk yok", "event_age": None},
                "MACD": {"detected": False, "state": "Son 5 barda aktif uyumsuzluk yok", "event_age": None},
                "SMI": {"detected": True, "state": "Negatif normal uyumsuzluk", "event_age": 3},
            }
        },
    },
    "momentum": [
        ["MACD", "değer", "Pozitif", "renk"],
        ["RSI", "değer", "50 üzeri", "renk"],
    ],
    "trend_volatility_volume": [["ADX/DMI", "değer", "+DI üstün", "renk"]],
    "technical_commentary": {"headline": "Denge rejiminde hacim ve kabul teyidi bekleniyor."},
}


class TelegramTests(unittest.TestCase):
    def _send_and_payload(self, thread_id: str | None) -> dict:
        environment = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "-1003502567927",
            "TELEGRAM_SEND_CAPTION": "1",
        }
        if thread_id is not None:
            environment["TELEGRAM_MESSAGE_THREAD_ID"] = thread_id
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(STATUS)),
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.BytesIO(b"png")),
            patch("src.send_telegram.render_analyst_cards", return_value=[Path("c1.png"), Path("c2.png"), Path("c3.png")]),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        return post.call_args_list[-1].kwargs["data"]

    def test_general_topic_omits_message_thread_id(self) -> None:
        payload = self._send_and_payload(None)
        self.assertNotIn("message_thread_id", payload)

    def test_explicit_topic_adds_message_thread_id(self) -> None:
        payload = self._send_and_payload("99")
        self.assertEqual(payload["message_thread_id"], "99")

    def test_caption_contains_active_divergence(self) -> None:
        payload = self._send_and_payload(None)
        self.assertIn("SMI Negatif normal uyumsuzluk (3 bar)", payload["caption"])

    def test_caption_contains_technical_commentary(self) -> None:
        payload = self._send_and_payload(None)
        self.assertIn("Teknik yorum:", payload["caption"])
        self.assertIn("Denge rejiminde hacim ve kabul teyidi bekleniyor.", payload["caption"])
        self.assertLessEqual(len(payload["caption"]), 1024)

    def test_long_caption_is_clipped_to_telegram_limit(self) -> None:
        status = json.loads(json.dumps(STATUS))
        status["technical_commentary"]["headline"] = "Uzun teknik yorum. " * 200
        environment = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "-1003502567927",
            "TELEGRAM_SEND_CAPTION": "1",
        }
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(status)),
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.BytesIO(b"png")),
            patch("src.send_telegram.render_analyst_cards", return_value=[Path("c1.png"), Path("c2.png"), Path("c3.png")]),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        caption = post.call_args_list[-1].kwargs["data"]["caption"]
        self.assertLessEqual(len(caption), CAPTION_LIMIT)
        self.assertTrue(caption.endswith("…"))

    def _send_with_environment(self, environment: dict, status: dict):
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(status)),
            patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.BytesIO(b"png")),
            patch("src.send_telegram.render_analyst_cards", return_value=[Path("c1.png"), Path("c2.png"), Path("c3.png")]),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        return post

    def test_three_cards_and_report_are_sent_as_four_photos(self) -> None:
        environment = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "-1003502567927"}
        post = self._send_with_environment(environment, json.loads(json.dumps(STATUS)))
        self.assertEqual(post.call_count, 4)
        for call in post.call_args_list:
            self.assertIn("sendPhoto", call.args[0])

    def test_photos_carry_no_caption_by_default(self) -> None:
        environment = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "-1003502567927"}
        post = self._send_with_environment(environment, json.loads(json.dumps(STATUS)))
        for call in post.call_args_list:
            self.assertNotIn("caption", call.kwargs["data"])

    def test_captions_can_be_enabled_with_environment_flag(self) -> None:
        environment = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "-1003502567927",
            "TELEGRAM_SEND_CAPTION": "1",
        }
        post = self._send_with_environment(environment, json.loads(json.dumps(STATUS)))
        self.assertIn("Analist Kartı", post.call_args_list[0].kwargs["data"]["caption"])
        self.assertIn("Teknik Piyasa Durumu", post.call_args_list[-1].kwargs["data"]["caption"])

    def test_text_detail_is_disabled_by_default(self) -> None:
        status = json.loads(json.dumps(STATUS))
        status["technical_commentary"]["telegram_detail"] = "🧭 Analist Notu\nAyrıntılı okuma metni."
        environment = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "-1003502567927"}
        post = self._send_with_environment(environment, status)
        endpoints = [call.args[0] for call in post.call_args_list]
        self.assertFalse(any("sendMessage" in endpoint for endpoint in endpoints))

    def test_text_detail_can_be_enabled_with_environment_flag(self) -> None:
        status = json.loads(json.dumps(STATUS))
        status["technical_commentary"]["telegram_detail"] = "🧭 Analist Notu\nAyrıntılı okuma metni."
        environment = {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "-1003502567927",
            "TELEGRAM_SEND_TEXT_DETAIL": "1",
        }
        post = self._send_with_environment(environment, status)
        self.assertEqual(post.call_count, 5)
        self.assertIn("sendMessage", post.call_args_list[-1].args[0])
        self.assertIn("Ayrıntılı okuma metni.", post.call_args_list[-1].kwargs["data"]["text"])

    def test_split_message_respects_limit_and_keeps_content(self) -> None:
        text = "\n".join(f"satır {index} " + "x" * 80 for index in range(150))
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= MESSAGE_LIMIT for part in parts))
        self.assertIn("satır 149", parts[-1])


if __name__ == "__main__":
    unittest.main()
