from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analyst_card import render_analyst_cards
from src.telegram_client import (
    build_caption,
    send_analyst_cards,
    send_report_detail,
    send_report_pages,
)


def caption(status: dict) -> str:
    return build_caption(status)


def send(image_path: Path, json_path: Path, card_directory: Path | None = None) -> None:
    """Önce iki teknik rapor sayfası, ardından iki analist kartı gönderir."""
    status = json.loads(json_path.read_text(encoding="utf-8"))
    directory = card_directory or image_path.parent
    cards = render_analyst_cards(status, directory)
    pages = [Path(item) for item in status.get("report_images", [])] or [image_path]
    sent = send_report_pages(pages, status) + send_analyst_cards(cards, status)
    detail_sent = send_report_detail(status)
    print(f"{sent} görsel gönderildi." + (" Ayrıntılı metin de iletildi." if detail_sent else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="reports/technical_report.png")
    parser.add_argument("--json", default="reports/technical_report.json")
    parser.add_argument("--card-dir", default="reports")
    args = parser.parse_args()
    send(Path(args.image), Path(args.json), Path(args.card_dir))


if __name__ == "__main__":
    main()
