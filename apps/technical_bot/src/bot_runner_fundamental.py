"""Production technical bot router for fundamental, research, scan history and legacy aliases.

The long-running technical listener remains in ``bot_runner``. This wrapper owns
user-facing research commands and patches scan artifact access so the bot reads
the outputs produced by the active scan workflow instead of stale local files.
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
SCAN_ARTIFACT_PREFIXES = ("bist-tarama", "bist-teknik-tarama")

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


def handle_research(chat_id: int, args: list[str], command: str = "analiz") -> None:
    ticker, error = _validate_ticker(args, command)
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


def list_scan_artifacts(limit: int = 10) -> list[dict[str, object]]:
    """Return current and legacy scan artifacts, newest first."""
    token = base.os.getenv("GITHUB_TOKEN", "")
    repository = base.os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repository:
        return []
    response = base.requests.get(
        f"https://api.github.com/repos/{repository}/actions/artifacts",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        params={"per_page": 100},
        timeout=30,
    )
    if not response.ok:
        return []
    artifacts = [
        item
        for item in response.json().get("artifacts", [])
        if any(str(item.get("name", "")).startswith(prefix) for prefix in SCAN_ARTIFACT_PREFIXES)
        and not item.get("expired")
    ]
    artifacts.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return artifacts[:limit]


def _latest_scan_payload() -> dict[str, object] | None:
    artifacts = list_scan_artifacts(limit=1)
    if artifacts:
        payload = base.download_scan_json(artifacts[0])
        if payload:
            return payload
    try:
        return json.loads(base.SCREENER_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return None


def handle_list(chat_id: int) -> None:
    """Render the newest scan, preferring the active workflow artifact."""
    payload = _latest_scan_payload()
    if not payload:
        base.reply(chat_id, "Henüz kayıtlı bir tarama sonucu yok. /tara ile yeni tarama başlatabilirsiniz.")
        return
    if not payload.get("results"):
        base.reply(chat_id, "Son taramada eşleşme yok.")
        return
    cards = base.render_scan_cards(
        payload,
        base.REPORTS_DIR / "komut",
        payload.get("universe_source", "borsapy"),
        float(payload.get("elapsed_seconds", 0.0)),
        title="Son Tarama — Tam Liste",
        limit=60,
        stem="liste_card",
    )
    base.standardize_pages(cards)
    base.send_analyst_cards(cards, {})


def execute(command, intervals: set[str]) -> None:
    if command.name in {"temel", "fundamental", "mali"}:
        handle_fundamental(command.chat_id, command.args)
        return
    if command.name in {"analiz", "arastir", "research", "rapor"}:
        public_command = "rapor" if command.name == "rapor" else "analiz"
        handle_research(command.chat_id, command.args, public_command)
        return
    _BASE_EXECUTE(command, intervals)


def main() -> None:
    base.HELP_TEXT = (
        "Kullanılabilir komutlar:\n"
        "/analiz SEMBOL — temel + bilanço + değerleme + MA + teknik yapı + risk\n"
        "/rapor SEMBOL — /analiz ile aynı güncel araştırma paketi\n"
        "/temel SEMBOL — sektör uyarlamalı temel analiz ve radar kartı\n"
        "/tara [aralık] — yeni tarama başlatır (boşsa saate göre seçilir)\n"
        "/liste — son tamamlanan taramanın tam listesi\n"
        "/gecmis [no] — geçmiş taramalar (numarasız: liste)\n"
        "/takip SEMBOL [aralık] — seviye uyarısı için takibe alır\n"
        "/takip sil SEMBOL — takipten çıkarır\n"
        "/esik [ad değer] — tarama eşikleri (ör. /esik rvol 2.0)\n"
        "/durum — bot ve tarama durumu\n"
        "/yardim — bu mesaj\n\n"
        "Takip/tarama aralıkları: 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1wk, 1mo"
    )
    # The active scan workflow owns scan output. Patch the legacy base helpers so
    # /liste and /gecmis read that workflow's artifacts instead of a stale cache.
    base.list_scan_artifacts = list_scan_artifacts
    base.handle_list = handle_list
    base.execute = execute
    base.main()


if __name__ == "__main__":
    main()
