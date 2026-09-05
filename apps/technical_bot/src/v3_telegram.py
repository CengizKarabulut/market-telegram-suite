from __future__ import annotations

from src.telegram_client import send_text


def send_v3_preview(text: str, *, symbol: str, interval_label: str) -> None:
    """Reader-facing V4 önizlemesini görselsiz, yalnız analist metni olarak yollar."""
    del symbol, interval_label  # metadata report/artifact içinde korunur; mesajda tekrar edilmez.
    send_text(text)
