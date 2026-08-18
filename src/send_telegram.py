from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.analyst_card import render_analyst_card
from src.telegram_client import (
    build_caption,
    send_analyst_card,
    send_photo,
    send_report_detail,
)


def caption(status: dict) -> str:
    return build_caption(status)


def send(image_path: Path, json_path: Path, card_path: Path | None = None) -> None:
    status = json.loads(json_path.read_text(encoding="utf-8"))
    send_photo(image_path, status)
    card = render_analyst_card(status, card_path or image_path.with_name("analyst_card.png"))
    send_analyst_card(card, status)
    detail_sent = send_report_detail(status)
    print("Telegram raporu ve analist kartı gönderildi." + (" Ayrıntılı metin de iletildi." if detail_sent else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="reports/technical_report.png")
    parser.add_argument("--json", default="reports/technical_report.json")
    parser.add_argument("--card", default="reports/analyst_card.png")
    args = parser.parse_args()
    send(Path(args.image), Path(args.json), Path(args.card))


if __name__ == "__main__":
    main()
