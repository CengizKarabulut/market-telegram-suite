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


def format_reader_telegram(report: dict[str, Any]) -> str:
    """Scanner/indikatör kodlarını göstermeyen analist dili Telegram görünümü."""
    symbol = str(report.get("symbol") or "—")
    label = str(report.get("interval_label") or report.get("interval") or "")
    price = _fmt_number(report.get("price"))
    try:
        change = float(report.get("change_pct"))
        change_text = f"%{change:+.2f}" if math.isfinite(change) else "—"
    except (TypeError, ValueError):
        change_text = "—"

    reader = report.get("reader_view") or {}
    if not reader.get("available", True):
        return "\n".join(
            [
                f"{symbol} — Analist Görüşü ({label})",
                f"Fiyat: {price} · Günlük değişim: {change_text}",
                "",
                str(reader.get("headline") or "Güvenilir analiz üretilemiyor."),
                str(reader.get("overview") or ""),
                str(reader.get("conclusion") or ""),
            ]
        ).strip()

    sections = [
        ("Genel görünüm", reader.get("overview")),
        ("Kısa vadede güç ne durumda?", reader.get("momentum")),
        ("Hareketin arkasında para var mı?", reader.get("participation")),
        ("Ek teknik koşullar ne söylüyor?", reader.get("screening")),
        ("Önemli fiyat bölgeleri", reader.get("levels")),
        ("Son seansta ne değişti?", reader.get("what_changed")),
        ("Sonuç", reader.get("conclusion")),
    ]

    lines = [
        f"{symbol} — Analist Görüşü ({label})",
        f"Fiyat: {price} · Değişim: {change_text}",
        "",
        str(reader.get("headline") or ""),
    ]
    for title, text in sections:
        cleaned = str(text or "").strip()
        if not cleaned:
            continue
        lines.extend(["", f"{title}:", cleaned])
    return "\n".join(lines).strip()
