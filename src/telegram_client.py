from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

DEFAULT_CHAT_ID = "-1003502567927"


def build_caption(status: dict[str, Any]) -> str:
    context = status["market_context"]
    profile = context["profile"]
    structure = context["structure"]
    bar_state = status.get("bar_state", {"label": "BİLİNMİYOR"})
    decision = status.get("decision_context", {})
    rs = decision.get("relative_strength", {})
    mtf = decision.get("multi_timeframe", {})
    liquidity = decision.get("liquidity", {})
    commentary = status.get("technical_commentary", {})
    atr_percentile = context["regime"].get("atr_percentile")
    bb_percentile = context["regime"].get("bb_percentile")
    volatility = (
        f"ATR perc %{atr_percentile:.0f} | BB perc %{bb_percentile:.0f}"
        if atr_percentile is not None and bb_percentile is not None
        else "—"
    )
    lines = [
        f"📊 {status['symbol']} — Teknik Piyasa Durumu",
        f"Fiyat: {status['price']:,.2f} ({status['change_pct']:+.2f}%)",
        f"Mum: {bar_state.get('label', 'BİLİNMİYOR')} | Piyasa: {bar_state.get('market_state', '—')}",
        "",
        f"Rejim: {context['regime']['state']}",
        f"Yapı: {structure['state']} — {structure['event']}",
        f"Konum: {profile['position']} | {profile.get('developing_acceptance', profile.get('acceptance', '—'))}",
        f"Katılım: RVOL {context['relative_volume']:.2f}x",
        f"Volatilite: {volatility}",
    ]
    if rs.get("available"):
        lines.append(f"RS vs {rs['benchmark']}: {rs['state']}")
    if mtf:
        lines.append(f"MTF: {mtf.get('state', '—')}")
    if liquidity:
        lines.append(f"Likidite: {liquidity.get('state', '—')}")
    divergence_items = context.get("divergences", {}).get("indicators", {})
    active_divergences = [
        f"{name} {item['state']} ({item['event_age']} bar)"
        for name, item in divergence_items.items()
        if item.get("detected")
    ]
    if active_divergences:
        lines.append("Uyumsuzluk: " + " | ".join(active_divergences))
    if commentary.get("headline"):
        lines.extend(["", "Teknik yorum:", commentary["headline"]])
    lines.extend(
        [
            "",
            "Yaklaşık OHLCV Volume Profile:",
            f"POC {profile['poc']:,.2f} | VAH {profile['vah']:,.2f} | VAL {profile['val']:,.2f}",
            "Gerçek footprint/delta değildir.",
            f"Kaynak: {status.get('data_provider', 'bilinmiyor')}",
            f"Bar: {status['timestamp']}",
            "",
            "Durum raporudur; otomatik AL/SAT puanı değildir. Yatırım tavsiyesi değildir.",
        ]
    )
    return "\n".join(lines)


def _destination() -> tuple[str, str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", DEFAULT_CHAT_ID).strip()
    thread_id = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN GitHub Actions Secret olarak tanımlanmalıdır.")
    return token, chat_id, thread_id


def send_photo(image_path: Path, status: dict[str, Any]) -> None:
    token, chat_id, thread_id = _destination()
    payload = {"chat_id": chat_id, "caption": build_caption(status)}
    if thread_id:
        payload["message_thread_id"] = thread_id
    with image_path.open("rb") as image:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            data=payload,
            files={"photo": (image_path.name, image, "image/png")},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"Telegram gönderimi başarısız: HTTP {response.status_code} — {response.text[:300]}")


def send_text(text: str) -> None:
    token, chat_id, thread_id = _destination()
    payload = {"chat_id": chat_id, "text": text}
    if thread_id:
        payload["message_thread_id"] = thread_id
    response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload, timeout=60)
    if not response.ok:
        raise RuntimeError(f"Telegram gönderimi başarısız: HTTP {response.status_code} — {response.text[:300]}")
