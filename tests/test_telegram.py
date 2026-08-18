import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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
        }
        if thread_id is not None:
            environment["TELEGRAM_MESSAGE_THREAD_ID"] = thread_id
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(STATUS)),
            patch.object(Path, "open", return_value=io.BytesIO(b"png")),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        return post.call_args.kwargs["data"]

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
        environment = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "-1003502567927"}
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(status)),
            patch.object(Path, "open", return_value=io.BytesIO(b"png")),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        caption = post.call_args.kwargs["data"]["caption"]
        self.assertLessEqual(len(caption), CAPTION_LIMIT)
        self.assertTrue(caption.endswith("…"))

    def test_detail_message_is_sent_after_photo(self) -> None:
        status = json.loads(json.dumps(STATUS))
        status["technical_commentary"]["telegram_detail"] = "🧭 Analist Notu\nAyrıntılı okuma metni."
        environment = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "-1003502567927"}
        response = Mock(ok=True, status_code=200, text='{"ok":true}')
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(Path, "read_text", return_value=json.dumps(status)),
            patch.object(Path, "open", return_value=io.BytesIO(b"png")),
            patch("src.telegram_client.requests.post", return_value=response) as post,
        ):
            send(Path("report.png"), Path("report.json"))
        self.assertEqual(post.call_count, 2)
        self.assertIn("sendPhoto", post.call_args_list[0].args[0])
        self.assertIn("sendMessage", post.call_args_list[1].args[0])
        text = post.call_args_list[1].kwargs["data"]["text"]
        self.assertIn("Ayrıntılı Teknik Okuma", text)
        self.assertIn("Ayrıntılı okuma metni.", text)

    def test_split_message_respects_limit_and_keeps_content(self) -> None:
        text = "\n".join(f"satır {index} " + "x" * 80 for index in range(150))
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= MESSAGE_LIMIT for part in parts))
        self.assertIn("satır 149", parts[-1])


if __name__ == "__main__":
    unittest.main()
