from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from src.telegram_client import DEFAULT_CHAT_ID, clip, send_text


def _destination() -> tuple[str, str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip() or DEFAULT_CHAT_ID
    thread_id = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN V3 Telegram gönderimi için tanımlı değil.")
    return token, chat_id, thread_id


def send_v3_card(image_path: Path, caption: str = "") -> None:
    token, chat_id, thread_id = _destination()
    payload: dict[str, Any] = {"chat_id": chat_id}
    if caption.strip():
        payload["caption"] = clip(caption.strip(), 1024)
    if thread_id:
        payload["message_thread_id"] = thread_id
    with image_path.open("rb") as image:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=payload,
            files={"photo": (image_path.name, image, "image/png")},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(
            f"V3 Telegram kart gönderimi başarısız: HTTP {response.status_code} — {response.text[:300]}"
        )


def send_v3_preview(text: str, image_path: Path, *, symbol: str, interval_label: str) -> None:
    """Gerçek-veri V3 çıktısını aynı Telegram hedefinde metin + kart olarak yollar."""
    send_text(f"🧪 V3 GERÇEK VERİ DENEMESİ\n\n{text}")
    send_v3_card(
        image_path,
        caption=(
            f"🧪 {symbol} — V3 Preview ({interval_label})\n"
            "Yeni Market Analysis Engine deneme kartı. Production /rapor akışından ayrıdır."
        ),
    )
