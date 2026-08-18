from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analyst_card import render_analyst_cards
from src.telegram_client import (
    build_caption,
    send_analyst_cards,
    send_photo,
    send_report_detail,
)


def caption(status: dict) -> str:
    return build_caption(status)


def send(image_path: Path, json_path: Path, card_directory: Path | None = None) -> None:
    """Önce okunabilir kart sayfalarını, ardından ayrıntılı teknik raporu gönderir."""
    status = json.loads(json_path.read_text(encoding="utf-8"))
    cards = render_analyst_cards(status, card_directory or image_path.parent)
    sent = send_analyst_cards(cards, status)
    send_photo(image_path, status)
    detail_sent = send_report_detail(status)
    print(f"{sent} analist kartı ve teknik rapor gönderildi." + (" Ayrıntılı metin de iletildi." if detail_sent else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="reports/technical_report.png")
    parser.add_argument("--json", default="reports/technical_report.json")
    parser.add_argument("--card-dir", default="reports")
    args = parser.parse_args()
    send(Path(args.image), Path(args.json), Path(args.card_dir))


if __name__ == "__main__":
    main()
