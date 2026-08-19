"""Telegram bot çalıştırıcısı.

Yeni komutları toplar, yetkilendirir ve yerine getirir. Tarama gibi uzun süren
işler bu süreçte çalıştırılmaz; ilgili GitHub Actions iş akışı tetiklenir ve
kullanıcıya bilgi verilir. Böylece bot yoklaması kısa ve öngörülebilir kalır.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from src.analyst_card import render_analyst_cards, standardize_pages
from src.intervals import INTERVALS, resolve
from src.scan_card import render_scan_cards
from src.stock_dashboard import (
    ScanConfig,
    build_status,
    calculate_indicators,
    download_prices,
    render_report_pages,
)
from src.telegram_bot import (
    HELP_TEXT,
    fetch_updates,
    is_authorized,
    load_offset,
    parse_command,
    save_offset,
    validate_report_args,
    validate_scan_args,
)
from src.telegram_client import send_analyst_cards

REPORTS_DIR = Path("reports")
SCREENER_JSON = REPORTS_DIR / "screener.json"
MAX_COMMANDS_PER_RUN = 5


def reply(chat_id: int, text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    thread = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "").strip()
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if thread:
        payload["message_thread_id"] = int(thread)
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, timeout=30)


def dispatch_scan(intervals: str) -> tuple[bool, str]:
    """Tarama iş akışını GitHub API üzerinden tetikler.

    Tarama 25+ dakika sürdüğü için bot yoklamasının içinde çalıştırılamaz.
    """
    token = os.getenv("GITHUB_TOKEN", "")
    repository = os.getenv("GITHUB_REPOSITORY", "")
    if not token or not repository:
        return False, "Tarama tetiklenemedi: GitHub kimlik bilgisi yok."
    response = requests.post(
        f"https://api.github.com/repos/{repository}/actions/workflows/scheduled-watchlist.yml/dispatches",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"ref": os.getenv("GITHUB_REF_NAME", "main"), "inputs": {"interval": intervals, "universe": "auto", "limit": "0"}},
        timeout=30,
    )
    if response.status_code == 204:
        return True, f"Tarama başlatıldı ({intervals}). Sonuç 25-30 dakika içinde bu gruba düşecek."
    return False, f"Tarama tetiklenemedi: HTTP {response.status_code} — {response.text[:150]}"


def handle_report(chat_id: int, ticker: str, interval: str) -> None:
    reply(chat_id, f"{ticker} raporu hazırlanıyor ({interval})… bu işlem yaklaşık bir dakika sürer.")
    config = ScanConfig(ticker=ticker, market="BIST", interval=interval, report_detail="kompakt")
    symbol, prices = download_prices(config)
    data = calculate_indicators(prices, interval)
    status = build_status(data, config, symbol)
    target = REPORTS_DIR / "komut" / ticker
    pages = render_report_pages(data, status, target, f"{ticker}_rapor")
    cards = render_analyst_cards(status, target, f"{ticker}_kart")
    standardize_pages(pages + cards)
    send_analyst_cards(pages + cards, status)


def handle_list(chat_id: int) -> None:
    if not SCREENER_JSON.exists():
        reply(chat_id, "Henüz kayıtlı bir tarama sonucu yok. /tara ile yeni tarama başlatabilirsiniz.")
        return
    payload = json.loads(SCREENER_JSON.read_text(encoding="utf-8"))
    if not payload.get("results"):
        reply(chat_id, "Son taramada eşleşme yok.")
        return
    cards = render_scan_cards(
        payload,
        REPORTS_DIR / "komut",
        payload.get("universe_source", "borsapy"),
        float(payload.get("elapsed_seconds", 0.0)),
        title="Son Tarama — Tam Liste",
        limit=60,
        stem="liste_card",
    )
    standardize_pages(cards)
    send_analyst_cards(cards, {})


def execute(command, intervals: set[str]) -> None:
    chat_id = command.chat_id
    if command.name in {"yardim", "yardım", "help", "start"}:
        reply(chat_id, HELP_TEXT)
        return
    if command.name == "rapor":
        ticker, interval, error = validate_report_args(command.args, intervals)
        if error:
            reply(chat_id, error)
            return
        handle_report(chat_id, ticker, interval)
        return
    if command.name in {"tara", "tarama"}:
        selection, error = validate_scan_args(command.args, intervals)
        if error:
            reply(chat_id, error)
            return
        _, message = dispatch_scan(selection)
        reply(chat_id, message)
        return
    if command.name in {"liste", "list"}:
        handle_list(chat_id)
        return
    reply(chat_id, f"Bilinmeyen komut: /{command.name}\n\n{HELP_TEXT}")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN tanımlı değil.")
    from src.telegram_bot import allowed_users

    allowed = allowed_users()
    offset = load_offset()
    updates = fetch_updates(token, offset)
    if not updates:
        print("Yeni komut yok.")
        return

    highest = offset
    handled = 0
    for update in updates:
        highest = max(highest, int(update.get("update_id", 0)))
        command = parse_command(update)
        if command is None:
            continue
        if not is_authorized(command, allowed):
            print(f"Yetkisiz komut atlandı: /{command.name} — {command.user_name} ({command.user_id})")
            continue
        if handled >= MAX_COMMANDS_PER_RUN:
            # Tek yoklamada sınırsız komut işlemek koşu süresini öngörülemez kılar.
            print("Bu turda komut sınırına ulaşıldı; kalanlar sonraki turda işlenecek.")
            highest = int(update.get("update_id", 0)) - 1
            break
        print(f"Komut: /{command.name} {' '.join(command.args)} — {command.user_name}")
        started = time.perf_counter()
        try:
            execute(command, set(INTERVALS))
        except Exception as error:  # noqa: BLE001 -- tek komut botu durdurmamalı
            print(f"  hata: {type(error).__name__}: {error}")
            reply(command.chat_id, f"Komut çalıştırılamadı: {type(error).__name__}. Ayrıntı iş akışı kaydında.")
        print(f"  süre: {time.perf_counter() - started:.1f} sn")
        handled += 1
    save_offset(highest)
    print(f"{handled} komut işlendi. Son güncelleme kimliği: {highest}")


if __name__ == "__main__":
    resolve("1d")  # aralık tablosunun yüklendiğini doğrular
    main()
