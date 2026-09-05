from __future__ import annotations

import math
import re
from typing import Any

from .models import MarketState
from .reader_narrative import build_reader_narrative


def _fmt_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(number):
        return "—"
    return f"{number:.{digits}f}".replace(".", ",")


def attach_reader_view(state: MarketState, report: dict[str, Any]) -> dict[str, Any]:
    """Canonical raporu bozmadan sade kullanıcı anlatımını ekler."""
    result = dict(report)
    result["reader_view"] = build_reader_narrative(state)
    return result


def _sentences(text: Any) -> list[str]:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", cleaned) if item.strip()]


def _normalized_sentence(text: str) -> str:
    return re.sub(r"[^a-z0-9çğıöşü]+", " ", text.casefold()).strip()


def _meaningful_change_sentences(reader: dict[str, Any]) -> list[str]:
    """Aynı ivme/hacim bilgisini paragrafta ikinci kez söylemeden yeni değişimi korur."""
    momentum = str(reader.get("momentum") or "").casefold()
    participation = str(reader.get("participation") or "").casefold()
    result: list[str] = []
    for sentence in _sentences(reader.get("what_changed")):
        lowered = sentence.casefold()
        momentum_overlap = any(
            token in lowered and token in momentum
            for token in ("ivme", "momentum", "alım isteği")
        )
        volume_overlap = "hacim" in lowered and "hacim" in participation
        if momentum_overlap or volume_overlap:
            continue
        result.append(sentence)
    return result


def _polish_paragraph(text: str) -> str:
    polished = " ".join(text.split())
    polished = polished.replace("Görünümün iyileşmesi için Önce ", "Görünümün iyileşmesi için önce ")
    # Reader katmanı Türkçe olduğu için ondalık gösterimini de Türkçeleştiriyoruz.
    polished = re.sub(r"(?<!\d)(\d+)\.(\d{1,2})(?!\d)", r"\1,\2", polished)
    return polished.strip()


def _paragraph(reader: dict[str, Any]) -> str:
    """Reader bölümlerini başlıksız, tek akıcı analist paragrafında birleştirir."""
    parts: list[str] = []
    seen: set[str] = set()

    def append_sentences(value: Any) -> None:
        values = value if isinstance(value, (list, tuple)) else [value]
        for item in values:
            for sentence in _sentences(item):
                normalized = _normalized_sentence(sentence)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                parts.append(sentence)

    append_sentences(reader.get("headline"))
    append_sentences(reader.get("overview"))
    append_sentences(reader.get("momentum"))
    append_sentences(reader.get("participation"))
    append_sentences(reader.get("screening"))
    append_sentences(_meaningful_change_sentences(reader))
    append_sentences(reader.get("levels"))
    append_sentences(reader.get("conclusion"))
    return _polish_paragraph(" ".join(parts))


def format_reader_telegram(report: dict[str, Any]) -> str:
    """Scanner/indikatör adlarını göstermeyen tek-paragraf analist görünümü."""
    symbol = str(report.get("symbol") or "—")
    label = str(report.get("interval_label") or report.get("interval") or "")
    price = _fmt_number(report.get("price"))
    try:
        change = float(report.get("change_pct"))
        change_text = f"{change:+.2f}%".replace(".", ",") if math.isfinite(change) else "—"
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
