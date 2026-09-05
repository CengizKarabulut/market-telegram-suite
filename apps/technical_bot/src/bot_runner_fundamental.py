"""Technical bot entry point extended with fundamental and research commands.

The existing technical command runner stays intact. New commands are routed in a
small wrapper so production technical scans/listeners keep their current
behaviour while the research layer evolves independently.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import bot_runner as base
from src.fundamental_analysis import build_fundamental_report
from src.fundamental_card import render_fundamental_card
from src.fundamental_quality import apply_coverage_policy
from src.fundamental_telegram import send_fundamental_card
from src.moving_average_card import render_moving_average_card
from src.research_card import render_research_card
from src.research_chart import render_research_chart
from src.research_risk import build_research_report
from src.research_telegram import send_research_bundle
from src.research_theme import apply_white_theme
from src.telegram_bot import VALID_TICKER

_BASE_EXECUTE = base.execute

# One visual language for /temel and /analiz. Pine indicator colours are kept;
# only research canvas/panel/text colours are changed to the white theme.
apply_white_theme()


def _validate_ticker(args: list[str], command: str = "temel") -> tuple[str | None, str | None]:
    example = f"/{command} GARAN"
    if not args:
        return None, f"Sembol belirtilmedi. Örnek: {example}"
    ticker = args[0].strip().upper().removesuffix(".IS")
    if not VALID_TICKER.match(ticker):
        return None, f"Geçersiz sembol: {args[0]}. Örnek: {example}"
    if len(args) > 1:
        return None, f"Bu analiz zaman diliminden bağımsızdır. Kullanım: {example}"
    return ticker, None


def handle_fundamental(chat_id: int, args: list[str]) -> None:
    ticker, error = _validate_ticker(args, "temel")
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


def handle_research(chat_id: int, args: list[str]) -> None:
    ticker, error = _validate_ticker(args, "analiz")
    if error or ticker is None:
        base.reply(chat_id, error or "Geçersiz sembol.")
        return

    # Intentionally no pre-report text message here: the user-facing bundle must
    # open with visuals, followed by analyst commentary.
    report = build_research_report(ticker)
    target = base.REPORTS_DIR / "komut" / ticker
    target.mkdir(parents=True, exist_ok=True)

    summary_image = render_research_card(report, target / f"{ticker}_arastirma.png")
    fundamental_image = render_fundamental_card(report.fundamental, target / f"{ticker}_temel.png")
    ma_image, ma_snapshot = render_moving_average_card(ticker, target / f"{ticker}_ortalamalar.png")
    technical_image = render_research_chart(ticker, report, target / f"{ticker}_teknik_yapi.png")
    payload = report.to_dict()
    payload["moving_averages"] = ma_snapshot
    Path(target / f"{ticker}_arastirma.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    send_research_bundle(summary_image, fundamental_image, ma_image, technical_image, report)


def execute(command, intervals: set[str]) -> None:
    if command.name in {"temel", "fundamental", "mali"}:
        handle_fundamental(command.chat_id, command.args)
        return
    if command.name in {"analiz", "arastir", "research"}:
        handle_research(command.chat_id, command.args)
        return
    _BASE_EXECUTE(command, intervals)


def main() -> None:
    fundamental_help = "/temel SEMBOL — sektör uyarlamalı temel analiz ve radar kartı"
    research_help = "/analiz SEMBOL — temel + bilanço + değerleme + MA tablosu + teknik yapı + risk"
    addition = ""
    if fundamental_help not in base.HELP_TEXT:
        addition += fundamental_help + "\n"
    if research_help not in base.HELP_TEXT:
        addition += research_help + "\n"
    if addition:
        base.HELP_TEXT = base.HELP_TEXT.replace(
            "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)\n",
            "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)\n" + addition,
        )
    base.execute = execute
    base.main()


if __name__ == "__main__":
    main()
