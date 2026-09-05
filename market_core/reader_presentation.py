from __future__ import annotations

import math
from typing import Any

from .models import MarketState
from .reader_narrative import build_reader_narrative


def _fmt_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:.{digits}f}" if math.isfinite(number) else "—"


def attach_reader_view(state: MarketState, report: dict[str, Any]) -> dict[str, Any]:
    """Canonical raporu bozmadan sade kullanıcı anlatımını ekler."""
    result = dict(report)
    result["reader_view"] = build_reader_narrative(state)
    return result


def _paragraph(reader: dict[str, Any]) -> str:
    """Reader bölümlerini başlıksız, tek akıcı analist paragrafında birleştirir."""
    ordered = (
        "headline",
        "overview",
        "momentum",
        "participation",
        "screening",
        "what_changed",
        "levels",
        "conclusion",
    )
    parts: list[str] = []
    seen: set[str] = set()
    for key in ordered:
        text = str(reader.get(key) or "").strip()
        if not text:
            continue
        normalized = " ".join(text.lower().split())
        if normalized in seen:
            continue
        seen.add(normalized)
        parts.append(text)
    return " ".join(parts)


def format_reader_telegram(report: dict[str, Any]) -> str:
    """Scanner/indikatör adlarını göstermeyen tek-paragraf analist görünümü."""
    symbol = str(report.get("symbol") or "—")
    label = str(report.get("interval_label") or report.get("interval") or "")
    price = _fmt_number(report.get("price"))
    try:
        change = float(report.get("change_pct"))
        change_text = f"%{change:+.2f}" if math.isfinite(change) else "—"
    except (TypeError, ValueError):
        change_text = "—"

    reader = report.get("reader_view") or {}
    paragraph = _paragraph(reader)
    if not paragraph:
        paragraph = "Güvenilir bir analist değerlendirmesi üretmek için yeterli veri yok."

    return "\n".join(
        [
            f"{symbol} — Analist Görüşü ({label})",
            f"Fiyat: {price} · Değişim: {change_text}",
            "",
            paragraph,
        ]
    ).strip()
