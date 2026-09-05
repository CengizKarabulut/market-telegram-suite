"""Technical bot entry point extended with the /temel command.

Keeping the extension in a small wrapper lets the existing, well-tested command
runner remain unchanged while the new fundamental workflow matures.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import bot_runner as base
from src.fundamental_analysis import build_fundamental_report
from src.fundamental_card import render_fundamental_card
from src.fundamental_quality import apply_coverage_policy
from src.fundamental_telegram import send_fundamental_card
from src.telegram_bot import VALID_TICKER

_BASE_EXECUTE = base.execute


def _validate_ticker(args: list[str]) -> tuple[str | None, str | None]:
    if not args:
        return None, "Sembol belirtilmedi. Örnek: /temel GARAN"
    ticker = args[0].strip().upper().removesuffix(".IS")
    if not VALID_TICKER.match(ticker):
        return None, f"Geçersiz sembol: {args[0]}. Örnek: /temel GARAN"
    if len(args) > 1:
        return None, "Temel analiz zaman diliminden bağımsızdır. Kullanım: /temel GARAN"
    return ticker, None


def handle_fundamental(chat_id: int, args: list[str]) -> None:
    ticker, error = _validate_ticker(args)
    if error or ticker is None:
        base.reply(chat_id, error or "Geçersiz sembol.")
        return
    base.reply(chat_id, f"{ticker} temel analiz kartı hazırlanıyor…")
    report = apply_coverage_policy(build_fundamental_report(ticker))
    target = base.REPORTS_DIR / "komut" / ticker
    target.mkdir(parents=True, exist_ok=True)
    image = render_fundamental_card(report, target / f"{ticker}_temel.png")
    Path(target / f"{ticker}_temel.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    send_fundamental_card(image, report)


def execute(command, intervals: set[str]) -> None:
    if command.name in {"temel", "fundamental", "mali"}:
        handle_fundamental(command.chat_id, command.args)
        return
    _BASE_EXECUTE(command, intervals)


def main() -> None:
    help_line = "/temel SEMBOL — sektör uyarlamalı temel analiz ve radar kartı"
    if help_line not in base.HELP_TEXT:
        base.HELP_TEXT = base.HELP_TEXT.replace(
            "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)\n",
            "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)\n"
            + help_line
            + "\n",
        )
    base.execute = execute
    base.main()


if __name__ == "__main__":
    main()
