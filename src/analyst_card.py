"""Analist kartı görseli.

Telegram'da uzun düz metin yerine okunabilir bir kart üretir. Kart yalnızca
mevcut yorum çıktısını görselleştirir; yeni bir hesap veya iddia içermez.
Yükseklik içeriğe göre hesaplanır, böylece metin hiçbir zaman kırpılmaz.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BG = "#0f172a"
PANEL = "#111827"
CARD = "#16202e"
WHITE = "#f8fafc"
MUTED = "#cbd5e1"
ACCENT = "#38bdf8"
LIGHT_GREEN = "#22c55e"
LIGHT_RED = "#ef4444"
YELLOW = "#eab308"
GRAY = "#64748b"

CARD_WIDTH_INCHES = 12.0
DPI = 100
MARGIN = 0.55
LINE_HEIGHT = 0.245
TITLE_HEIGHT = 0.40
SECTION_GAP = 0.20


def tone_colour(tone: str) -> str:
    return {
        "positive": LIGHT_GREEN,
        "negative": LIGHT_RED,
        "warning": YELLOW,
        "neutral": MUTED,
    }.get(tone, MUTED)


def _wrap(text: str, font_size: int, width_inches: float) -> list[str]:
    """Metni kart genişliğine göre satırlara böler."""
    characters = max(int(width_inches * 72 / (font_size * 0.52)), 20)
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        lines.extend(textwrap.wrap(paragraph, characters) or [""])
    return lines


class _Block:
    def __init__(self, kind: str, text: str, font_size: int, colour: str, weight: str = "normal") -> None:
        self.kind = kind
        self.text = text
        self.font_size = font_size
        self.colour = colour
        self.weight = weight
        self.lines: list[str] = []

    def measure(self, width_inches: float) -> float:
        if self.kind == "gap":
            return SECTION_GAP
        if self.kind == "section":
            self.lines = [self.text]
            return TITLE_HEIGHT
        self.lines = _wrap(self.text, self.font_size, width_inches)
        return len(self.lines) * LINE_HEIGHT * (self.font_size / 12.0)


def _blocks(status: dict[str, Any]) -> list[_Block]:
    commentary = status.get("technical_commentary", {})
    setup = commentary.get("setup", {})
    scenario = commentary.get("scenario_map", {})
    labels = scenario.get("labels", {})
    clarity = commentary.get("clarity", {})
    levels = commentary.get("levels", {})
    plain = commentary.get("plain_summary", {})
    blocks: list[_Block] = []

    blocks.append(_Block("section", "SADE ÖZET", 15, ACCENT))
    blocks.append(_Block("body", plain.get("text", "—"), 13, WHITE))
    blocks.append(_Block("gap", "", 12, WHITE))

    blocks.append(_Block("section", "KURULUM", 15, ACCENT))
    blocks.append(
        _Block("body", f"{setup.get('name', '—')}  •  eğilim: {setup.get('bias', '—')}", 14, tone_colour(setup.get("tone", "neutral")), "bold")
    )
    if setup.get("description"):
        blocks.append(_Block("body", setup["description"], 12, MUTED))
    blocks.append(_Block("gap", "", 12, WHITE))

    blocks.append(_Block("section", "ANALİST NOTU", 15, ACCENT))
    for paragraph in str(commentary.get("analyst_note", "")).split("\n\n"):
        if paragraph.strip():
            blocks.append(_Block("body", paragraph.strip(), 11, WHITE))
            blocks.append(_Block("gap", "", 11, WHITE))

    blocks.append(_Block("section", "NEDEN BU OKUMA?", 15, ACCENT))
    blocks.append(_Block("body", commentary.get("reconciliation", "—"), 11, MUTED))
    blocks.append(_Block("gap", "", 12, WHITE))

    supporting = commentary.get("supporting_evidence", [])
    counter = commentary.get("counter_evidence", [])
    if supporting or counter:
        blocks.append(_Block("section", "KANIT DENGESİ", 15, ACCENT))
        for item in supporting:
            blocks.append(_Block("body", f"▲  {item['family']}: {item['state']}", 11, LIGHT_GREEN))
        for item in counter:
            blocks.append(_Block("body", f"▼  {item['family']}: {item['state']}", 11, LIGHT_RED))
        blocks.append(_Block("gap", "", 12, WHITE))

    clusters = levels.get("clusters", [])
    if clusters:
        blocks.append(_Block("section", "TEKNİK YOĞUNLAŞMA BÖLGELERİ", 15, ACCENT))
        for cluster in clusters[:4]:
            members = ", ".join(cluster.get("members", [])[:5])
            blocks.append(
                _Block(
                    "body",
                    f"{cluster['low']:,.2f} – {cluster['high']:,.2f}   {cluster.get('side', '')} ({cluster.get('strength', '')})   →  {members}",
                    11,
                    MUTED,
                )
            )
        blocks.append(_Block("gap", "", 12, WHITE))

    two_sided = str(setup.get("bias", "")) == "iki yönlü"
    for key, colour in (("strengthen", LIGHT_GREEN), ("weaken", LIGHT_RED), ("neutral", MUTED)):
        items = scenario.get(key, [])
        if not items:
            continue
        blocks.append(_Block("section", str(labels.get(key, key)).upper(), 14, ACCENT))
        for item in items:
            if two_sided and key == "strengthen":
                lowered = item.casefold()
                line_colour = LIGHT_GREEN if "yukarı" in lowered else LIGHT_RED if "aşağı" in lowered else MUTED
            else:
                line_colour = colour
            blocks.append(_Block("body", f"•  {item}", 11, line_colour))
        blocks.append(_Block("gap", "", 12, WHITE))

    changes = commentary.get("changes", [])
    if changes:
        blocks.append(_Block("section", "DÜNDEN BUGÜNE", 14, ACCENT))
        for item in changes:
            blocks.append(_Block("body", f"•  {item}", 11, MUTED))
        blocks.append(_Block("gap", "", 12, WHITE))

    blocks.append(
        _Block("body", f"Okuma netliği: {clarity.get('state', '—')} — {clarity.get('reason', '')}", 11, tone_colour(clarity.get("tone", "neutral")))
    )
    blocks.append(
        _Block("body", "Teknik durum yorumudur; yatırım tavsiyesi veya otomatik AL/SAT sinyali değildir.", 10, GRAY)
    )
    return blocks


def render_analyst_card(status: dict[str, Any], output: Path) -> Path:
    """Yorum çıktısını okunabilir bir PNG kartına dönüştürür."""
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    text_width = CARD_WIDTH_INCHES - 2 * MARGIN
    blocks = _blocks(status)
    heights = [block.measure(text_width) for block in blocks]
    header_height = 1.35
    total = header_height + sum(heights) + 2 * MARGIN

    figure = plt.figure(figsize=(CARD_WIDTH_INCHES, total), dpi=DPI, facecolor=BG)
    axes = figure.add_axes([0, 0, 1, 1])
    axes.set_xlim(0, CARD_WIDTH_INCHES)
    axes.set_ylim(0, total)
    axes.axis("off")
    axes.add_patch(
        FancyBboxPatch(
            (MARGIN * 0.4, MARGIN * 0.4),
            CARD_WIDTH_INCHES - MARGIN * 0.8,
            total - MARGIN * 0.8,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=CARD,
            edgecolor="#233046",
            linewidth=1.2,
        )
    )

    cursor = total - MARGIN
    symbol = status.get("symbol", "—")
    price = status.get("price", float("nan"))
    change = status.get("change_pct", 0.0)
    bar_state = status.get("bar_state", {})
    axes.text(MARGIN, cursor - 0.28, f"{symbol} — Analist Kartı", color=WHITE, fontsize=25, fontweight="bold", va="top")
    cursor -= 0.62
    change_colour = LIGHT_GREEN if change >= 0 else LIGHT_RED
    axes.text(MARGIN, cursor - 0.18, f"{price:,.2f}", color=WHITE, fontsize=19, fontweight="bold", va="top")
    axes.text(MARGIN + 1.55, cursor - 0.20, f"{change:+.2f}%", color=change_colour, fontsize=16, fontweight="bold", va="top")
    axes.text(
        MARGIN + 3.05,
        cursor - 0.20,
        f"{bar_state.get('label', '—')}  |  {status.get('timestamp', '—')}  |  {status.get('data_provider', '—')}",
        color=MUTED,
        fontsize=10,
        va="top",
    )
    cursor -= 0.55
    axes.plot([MARGIN, CARD_WIDTH_INCHES - MARGIN], [cursor, cursor], color="#233046", linewidth=1.4)
    cursor -= 0.18

    for block, height in zip(blocks, heights, strict=True):
        if block.kind == "gap":
            cursor -= height
            continue
        if block.kind == "section":
            axes.text(MARGIN, cursor - 0.20, block.text, color=block.colour, fontsize=block.font_size, fontweight="bold", va="top")
            cursor -= height
            continue
        step = LINE_HEIGHT * (block.font_size / 12.0)
        for line in block.lines:
            axes.text(MARGIN, cursor - step * 0.72, line, color=block.colour, fontsize=block.font_size, fontweight=block.weight, va="top")
            cursor -= step

    figure.savefig(output, facecolor=BG, dpi=DPI)
    plt.close(figure)
    return output
