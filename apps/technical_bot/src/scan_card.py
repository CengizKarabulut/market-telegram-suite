"""Tarama özeti görseli.

Tarama sonucunu analist kartlarıyla aynı tasarım diliyle bir PNG'ye dönüştürür;
böylece Telegram akışında metin ve görsel karışımı olmaz. Kart altyapısı
yeniden kullanıldığı için boyut eşitleme ve sayfalama kendiliğinden çalışır.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from src.analyst_card import (
    ACCENT,
    CARD_WIDTH_INCHES,
    GRAY,
    LIGHT_GREEN,
    LIGHT_RED,
    MARGIN,
    MUTED,
    WHITE,
    YELLOW,
    _Block,
    _paginate,
    render_analyst_card,
)
from src.plain_language import scan_line_plain
from src.screener import SCREENS


def _tone_for(item: dict[str, Any]) -> str:
    excess = item.get("excess_return_20")
    if isinstance(excess, (int, float)) and math.isfinite(float(excess)):
        if excess >= 3:
            return LIGHT_GREEN
        if excess <= -3:
            return LIGHT_RED
    return WHITE


def _summary_blocks(payload: dict[str, Any], universe_source: str, elapsed: float, limit: int) -> list[_Block]:
    labels = {name: SCREENS[name]["label"] for name in SCREENS}
    broken = len(payload.get("error_kinds", {}).get("ariza", []))
    illiquid = payload.get("illiquid", payload.get("filtered_out", 0))
    no_match = payload.get("no_match", 0)
    blocks = [
        _Block("section", "TARAMA ÖZETİ", 23, ACCENT),
        _Block(
            "body",
            f"Evren {payload['requested']} sembol ({universe_source}) · İşlenen {payload['processed']} · "
            f"Eşleşen {payload['matched']} · Likidite elemesi {illiquid} · Koşul karşılamayan {no_match} · "
            f"Arıza {broken} · Süre {elapsed / 60:.1f} dk",
            16,
            MUTED,
        ),
    ]
    freshness = payload.get("freshness", {})
    if freshness.get("stale"):
        age = freshness.get("age_minutes", 0) / 60
        blocks.append(
            _Block(
                "body",
                f"⚠ Son bar {age:.1f} saat önceye ait; seans dışı tarama. Hacim ve RVOL değerleri güncel katılımı yansıtmaz.",
                16,
                YELLOW,
                "bold",
            )
        )
    blocks.append(_Block("gap", "", 14, WHITE))
    results = payload.get("results", [])[:limit]
    if not results:
        blocks.append(_Block("body", "Bu taramada koşulları karşılayan sembol bulunamadı.", 18, MUTED))
        return blocks

    blocks.append(_Block("section", "EŞLEŞEN SEMBOLLER", 23, ACCENT))
    for index, item in enumerate(results, start=1):
        setup = str(item.get("setup", ""))
        tags = [labels.get(name, name) for name in item.get("screens", [])]
        tags = [tag for tag in tags if tag.casefold() != setup.casefold()]
        matched_intervals = item.get("matched_intervals", [])
        # Başlık: sembol ve fiyat. Teknik ayrıntılar aşağıya, sade anlatım öne alınır;
        # listeyi teknik analiz bilmeyen biri de okuyabilmelidir.
        blocks.append(_Block("body", f"{index}. {item['ticker']}   {item['close']:,.2f} TL", 19, _tone_for(item), "bold"))
        blocks.append(_Block("body", scan_line_plain(item), 15, WHITE))
        excess = item.get("excess_return_20")
        strength = f"XU100 {excess:+.1f}p" if isinstance(excess, (int, float)) and math.isfinite(float(excess)) else "XU100 —"
        technical = f"RVOL {item['rvol']:.2f}x · BB %{item['bb_width_percentile']:.0f} · {strength}"
        if matched_intervals:
            technical += f" · {' + '.join(matched_intervals)}"
        if setup:
            technical += f" · {setup}"
        if tags:
            technical += f" · {', '.join(tags)}"
        blocks.append(_Block("body", technical, 13, GRAY))
        for note in item.get("notes", [])[:1]:
            blocks.append(_Block("body", f"⚠ {note}", 13, YELLOW))
        blocks.append(_Block("gap", "", 11, WHITE))

    if payload["matched"] > len(results):
        blocks.append(_Block("body", f"… ve {payload['matched'] - len(results)} sembol daha (tam liste JSON çıktısında).", 15, MUTED))

    actions = payload.get("corporate_actions", [])
    if actions:
        blocks.append(
            _Block(
                "body",
                f"⛔ Bölünme/sermaye artırımı şüphesi nedeniyle taramaya alınmayan {len(actions)} sembol: "
                + ", ".join(actions[:8]),
                14,
                LIGHT_RED,
            )
        )
    gaps = payload.get("error_kinds", {})
    skipped = len(gaps.get("kisa_gecmis", [])) + len(gaps.get("veri_yok", []))
    if skipped:
        blocks.append(_Block("body", f"Taranamayan {skipped} sembol: yetersiz geçmiş veya veri yok.", 14, GRAY))
    if gaps.get("ariza"):
        blocks.append(_Block("body", "Gerçek hata veren semboller: " + ", ".join(gaps["ariza"][:8]), 14, YELLOW))
    blocks.append(_Block("gap", "", 12, WHITE))
    blocks.append(_Block("body", "Durum taramasıdır; AL/SAT sinyali veya yatırım tavsiyesi değildir.", 13, GRAY))
    return blocks


def render_scan_cards(
    payload: dict[str, Any],
    directory: Path,
    universe_source: str,
    elapsed: float,
    title: str = "BIST Teknik Tarama",
    limit: int = 15,
    stem: str = "scan_card",
) -> list[Path]:
    """Tarama özetini bir veya birkaç karta çizer."""
    directory.mkdir(parents=True, exist_ok=True)
    status = {
        "symbol": title,
        "header_line": payload.get("header_line", ""),
        "price": 0.0,
        "change_pct": 0.0,
        "timestamp": payload.get("timestamp", ""),
        "data_provider": universe_source,
        "bar_state": {"label": "TEYİTLİ", "is_live": False, "interval": payload.get("interval", "1d")},
        "report_detail": "dengeli",
    }
    blocks = _summary_blocks(payload, universe_source, elapsed, limit)
    text_width = CARD_WIDTH_INCHES - 2 * MARGIN
    budget = CARD_WIDTH_INCHES * 2.2 - 2.6
    chunks = _paginate(blocks, text_width, budget)
    paths: list[Path] = []
    for index, chunk in enumerate(chunks, start=1):
        label = "Tarama" if len(chunks) == 1 else f"Tarama {index}/{len(chunks)}"
        paths.append(render_analyst_card(status, directory / f"{stem}_{index}.png", chunk, label))
    return paths
