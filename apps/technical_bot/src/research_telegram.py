"""Telegram delivery for the integrated research report."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from src.research_engine import ResearchReport
from src.telegram_client import CAPTION_LIMIT, DEFAULT_CHAT_ID, caption_enabled, clip


def _destination() -> tuple[str, str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID).strip()
    thread_id = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN GitHub Actions Secret olarak tanımlanmalıdır.")
    return token, chat_id, thread_id


def _caption(report: ResearchReport) -> str:
    score = "—" if report.research_score is None else f"{report.research_score:.0f}/100"
    risk = "—" if report.main_risk is None else f"{report.main_risk.name} ({report.main_risk.score:.0f}/100)"
    financial = report.financial
    lines = [
        f"📚 {report.symbol} — Araştırma Özeti",
        f"Genel durum: {score} · veri kapsamı %{round(report.coverage * 100)}",
        f"Bilanço: {financial.get('balance_label', '—')} · Kâr kalitesi: {financial.get('earnings_quality_label', '—')}",
        f"Borç yönü: {financial.get('debt_direction', '—')}",
        f"Teknik: {report.technical.get('label', '—')} · Ana risk: {risk}",
        "",
        "Sonraki görseller: sektör uyarlamalı temel kart + teknik yapı grafiği. Otomatik AL/SAT değildir.",
    ]
    return clip("\n".join(lines), CAPTION_LIMIT)


def _send_photo(token: str, chat_id: str, thread_id: str, image_path: Path, caption: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id}
    if thread_id:
        payload["message_thread_id"] = thread_id
    if caption and caption_enabled():
        payload["caption"] = clip(caption, CAPTION_LIMIT)
    with image_path.open("rb") as image:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=payload,
            files={"photo": (image_path.name, image, "image/png")},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"Telegram araştırma gönderimi başarısız: HTTP {response.status_code} — {response.text[:300]}")
    try:
        return dict(response.json())
    except ValueError:
        return {"ok": True}


def send_research_bundle(
    summary_card: Path,
    fundamental_card: Path,
    technical_chart: Path,
    report: ResearchReport,
) -> tuple[dict[str, Any], ...]:
    """Send the summary first, then the fundamental and technical visuals."""
    token, chat_id, thread_id = _destination()
    results = [
        _send_photo(token, chat_id, thread_id, summary_card, _caption(report)),
        _send_photo(token, chat_id, thread_id, fundamental_card, f"{report.symbol} · Temel analiz / sektör profili"),
        _send_photo(token, chat_id, thread_id, technical_chart, f"{report.symbol} · Teknik yapı ve aktif kritik seviyeler"),
    ]
    return tuple(results)
