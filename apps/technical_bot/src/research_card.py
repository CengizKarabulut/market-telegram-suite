"""Mobile-first integrated research summary card."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src.research_engine import LevelZone, ResearchReport

BG = "#f4f7f8"
PANEL = "#ffffff"
TEXT = "#263238"
MUTED = "#78909c"
GRID = "#dfe7ea"
GREEN = "#2e9f6b"
RED = "#d9534f"
AMBER = "#d99a21"
TEAL = "#168d89"


def _colour(score: float | None) -> str:
    if score is None:
        return MUTED
    if score >= 70:
        return GREEN
    if score < 45:
        return RED
    return AMBER


def _stars(score: float | None) -> str:
    if score is None:
        return "☆☆☆☆☆"
    filled = max(0, min(5, round(score / 20)))
    return "★" * filled + "☆" * (5 - filled)


def _wrap(value: str, width: int = 78) -> str:
    return "\n".join(textwrap.wrap(str(value), width=width))


def _zone_text(zone: LevelZone) -> str:
    span = f"{zone.low:,.2f}" if abs(zone.high - zone.low) < 0.005 else f"{zone.low:,.2f}–{zone.high:,.2f}"
    return f"{span} · {zone.status} · {zone.score:.0f}/100 · {', '.join(zone.sources[:4])}"


def render_research_card(report: ResearchReport, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(8.5, 13.5), dpi=140, facecolor=BG)

    price = "—" if report.price is None else f"{report.price:,.2f}"
    score = "—" if report.research_score is None else f"{report.research_score:.0f}/100"
    fig.text(0.07, 0.955, f"{report.symbol} · {price}", fontsize=22, fontweight="bold", color=TEXT, va="top")
    fig.text(0.07, 0.923, _wrap(report.company_name, 50), fontsize=10.5, color=MUTED, va="top")
    fig.text(0.07, 0.883, "ARAŞTIRMA ÖZETİ", fontsize=10.5, color=TEAL, fontweight="bold")
    fig.text(0.07, 0.845, "Genel Durum", fontsize=13.5, color=TEXT, fontweight="bold")
    fig.text(0.58, 0.845, score, fontsize=18, color=_colour(report.research_score), fontweight="bold")
    fig.text(0.93, 0.845, _stars(report.research_score), fontsize=17, color=TEAL, ha="right")
    fig.text(0.07, 0.814, f"Veri kapsamı %{round(report.coverage * 100)}", fontsize=9.5, color=MUTED)

    ax = fig.add_axes([0.07, 0.49, 0.86, 0.30])
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0, 0),
            1,
            1,
            boxstyle="round,pad=0.015,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor=PANEL,
            edgecolor=GRID,
            linewidth=1.0,
        )
    )
    top, gap = 0.88, 0.19
    for index, dimension in enumerate(report.dimensions):
        y = top - index * gap
        number = "—" if dimension.score is None else f"{dimension.score:.0f}/100"
        ax.text(0.04, y, dimension.name, fontsize=13.2, fontweight="bold", color=TEXT, va="center")
        ax.text(0.48, y, number, fontsize=12.5, color=_colour(dimension.score), va="center")
        ax.text(0.96, y, dimension.label, fontsize=10.0, color=_colour(dimension.score), ha="right", va="center")
        ax.text(0.04, y - 0.055, _wrap(dimension.summary, 82), fontsize=8.4, color=MUTED, va="top")
        if index < len(report.dimensions) - 1:
            ax.plot([0.04, 0.96], [y - 0.095, y - 0.095], color="#edf1f3", linewidth=0.8)

    risk_ax = fig.add_axes([0.07, 0.345, 0.86, 0.115])
    risk_ax.axis("off")
    risk_ax.add_patch(
        FancyBboxPatch(
            (0, 0),
            1,
            1,
            boxstyle="round,pad=0.015,rounding_size=0.025",
            transform=risk_ax.transAxes,
            facecolor=PANEL,
            edgecolor=GRID,
            linewidth=1.0,
        )
    )
    if report.main_risk is None:
        risk_ax.text(0.04, 0.65, "Ana Risk", fontsize=12.5, fontweight="bold", color=TEXT)
        risk_ax.text(0.04, 0.30, "Risk verisi yetersiz.", fontsize=10.2, color=MUTED)
    else:
        risk_ax.text(0.04, 0.68, f"ANA RİSK · {report.main_risk.name}", fontsize=12.5, fontweight="bold", color=RED)
        risk_ax.text(0.94, 0.68, f"{report.main_risk.score:.0f}/100", fontsize=12.5, fontweight="bold", color=RED, ha="right")
        risk_ax.text(0.04, 0.28, _wrap(report.main_risk.evidence, 96), fontsize=9.6, color=TEXT, va="center")

    level_ax = fig.add_axes([0.07, 0.135, 0.86, 0.18])
    level_ax.axis("off")
    level_ax.text(0.0, 0.95, "KRİTİK SEVİYELER", fontsize=12.5, fontweight="bold", color=TEXT, va="top")
    y = 0.70
    if report.supports:
        for zone in report.supports[:2]:
            level_ax.text(0.0, y, f"✓ Destek  {_zone_text(zone)}", fontsize=9.5, color=GREEN, va="top")
            y -= 0.20
    else:
        level_ax.text(0.0, y, "Destek: yakın ve yeterli kalite puanlı aktif bölge yok.", fontsize=9.5, color=MUTED, va="top")
        y -= 0.20
    if report.resistances:
        for zone in report.resistances[:2]:
            level_ax.text(0.0, y, f"! Direnç  {_zone_text(zone)}", fontsize=9.5, color=RED, va="top")
            y -= 0.20
    else:
        level_ax.text(0.0, y, "Direnç: yakın ve yeterli kalite puanlı aktif bölge yok.", fontsize=9.5, color=MUTED, va="top")

    financial = report.financial
    fig.text(
        0.07,
        0.095,
        f"Bilanço: {financial.get('balance_label', '—')} · Kâr kalitesi: {financial.get('earnings_quality_label', '—')} · Borç: {financial.get('debt_direction', '—')}",
        fontsize=9.7,
        color=TEXT,
    )
    fig.text(0.07, 0.066, _wrap(report.note, 115), fontsize=8.1, color=MUTED, va="top")
    fig.text(
        0.5,
        0.022,
        "Teknik + bilanço + değerleme + şirket kalitesi + risk · otomatik AL/SAT değildir",
        fontsize=8.2,
        color=MUTED,
        ha="center",
    )
    fig.savefig(output, facecolor=BG, bbox_inches="tight", pad_inches=0.16)
    plt.close(fig)
    return output
