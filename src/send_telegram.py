from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.telegram_client import build_caption, send_photo, send_report_detail


def caption(status: dict) -> str:
    return build_caption(status)


def send(image_path: Path, json_path: Path) -> None:
    status = json.loads(json_path.read_text(encoding="utf-8"))
    send_photo(image_path, status)
    detail_sent = send_report_detail(status)
    print("Telegram raporu gönderildi." + (" Ayrıntılı analist notu da iletildi." if detail_sent else ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="reports/technical_report.png")
    parser.add_argument("--json", default="reports/technical_report.json")
    args = parser.parse_args()
    send(Path(args.image), Path(args.json))


if __name__ == "__main__":
    main()
