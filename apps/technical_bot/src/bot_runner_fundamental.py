"""Technical bot entry point for modern technical, fundamental and research commands.

Legacy scanning/list/history/watch/settings commands stay in ``bot_runner``. User-facing
single-stock analysis commands are routed here so ``/rapor`` no longer falls back to
the old ``stock_dashboard`` report motor.
"""

from __future__ import annotations

import json
from pathlib import Path

from src import bot_runner as base
from src.fundamental_analysis import build_fundamental_report
from src.fundamental_card import render_fundamental_card
from src.fundamental_quality import apply_coverage_policy
from src.fundamental_telegram import send_fundamental_card
from src.research_pipeline import build_research_bundle, build_technical_bundle
from src.research_telegram import send_research_bundle, send_technical_bundle
from src.research_theme import apply_white_theme
from src.telegram_bot import VALID_TICKER

_BASE_EXECUTE = base.execute

# One visual language for /temel, /rapor and /analiz. Pine indicator colours are
# kept; only research canvas/panel/text colours are changed to the white theme.
apply_white_theme()


def _validate_ticker(args: list[str], command: str) -> tuple[str | None, str | None]:
    example = f"/{command} GARAN"
    if not args:
        return None, f"Sembol belirtilmedi. Örnek: {example}"
    ticker = args[0].strip().upper().removesuffix(".IS")
    if not VALID_TICKER.match(ticker):
        return None, f"Geçersiz sembol: {args[0]}. Örnek: {example}"
    if len(args) > 1:
        return None, (
            f"/{command} çoklu zaman dilimli araştırma üretir; ayrıca aralık parametresi almaz. "
            f"Kullanım: {example}"
        )
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


def handle_technical(chat_id: int, args: list[str]) -> None:
    ticker, error = _validate_ticker(args, "rapor")
    if error or ticker is None:
        base.reply(chat_id, error or "Geçersiz sembol.")
        return

    # The modern technical package is intentionally built from the audited
    # research engine: daily main structure, weekly/monthly confirmation, MA
    # table and Pine-faithful indicator panels. Legacy stock_dashboard is not used.
    bundle = build_technical_bundle(ticker, base.REPORTS_DIR / "komut" / ticker / "teknik")
    send_technical_bundle(
        bundle.moving_average_card,
        bundle.technical_chart,
        bundle.report,
    )


def handle_research(chat_id: int, args: list[str]) -> None:
    ticker, error = _validate_ticker(args, "analiz")
    if error or ticker is None:
        base.reply(chat_id, error or "Geçersiz sembol.")
        return

    # Intentionally no pre-report text message: the user-facing bundle opens
    # with the complete visual evidence stack and then the analyst commentary.
    bundle = build_research_bundle(ticker, base.REPORTS_DIR / "komut" / ticker)
    send_research_bundle(
        bundle.summary_card,
        bundle.fundamental_card,
        bundle.moving_average_card,
        bundle.technical_chart,
        bundle.report,
        financial_card=bundle.financial_card,
        valuation_peer_card=bundle.valuation_peer_card,
    )


def execute(command, intervals: set[str]) -> None:
    if command.name in {"temel", "fundamental", "mali"}:
        handle_fundamental(command.chat_id, command.args)
        return
    if command.name in {"rapor", "teknik", "technical"}:
        handle_technical(command.chat_id, command.args)
        return
    if command.name in {"analiz", "arastir", "research"}:
        handle_research(command.chat_id, command.args)
        return
    _BASE_EXECUTE(command, intervals)


def main() -> None:
    old_report_help = "/rapor SEMBOL [aralık] — tek hisse teknik raporu (ör. /rapor THYAO 4h)"
    modern_report_help = (
        "/rapor SEMBOL — modern teknik araştırma: günlük yapı + haftalık/aylık teyit + "
        "MA tablosu + BB/AlphaTrend/MACD/SMI/RSI/OBV/ATR"
    )
    if old_report_help in base.HELP_TEXT:
        base.HELP_TEXT = base.HELP_TEXT.replace(old_report_help, modern_report_help)

    additions = (
        "/teknik SEMBOL — /rapor ile aynı modern teknik paket",
        "/temel SEMBOL — sektör uyarlamalı temel analiz ve radar kartı",
        (
            "/analiz SEMBOL — temel + bilanço oranları/skorları + değerleme/rakipler + "
            "MA tablosu + teknik yapı + risk"
        ),
    )
    anchor = modern_report_help + "\n"
    missing = [line for line in additions if line not in base.HELP_TEXT]
    if missing and anchor in base.HELP_TEXT:
        base.HELP_TEXT = base.HELP_TEXT.replace(anchor, anchor + "\n".join(missing) + "\n")

    base.execute = execute
    base.main()


if __name__ == "__main__":
    main()
