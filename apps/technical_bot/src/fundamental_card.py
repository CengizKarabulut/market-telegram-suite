"""Mobile-first fundamental analysis card renderer."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

from src.fundamental_analysis import Factor, FundamentalReport

BG = "#f5f7f8"
PANEL = "#ffffff"
TEXT = "#263238"
MUTED = "#78909c"
GRID = "#d9e1e5"
TEAL = "#42b8b5"
TEAL_DARK = "#168d89"
GREEN = "#2e9f6b"
RED = "#d9534f"
AMBER = "#d99a21"


def _stars(score: float | None) -> str:
    if score is None:
        return "☆☆☆☆☆"
    filled = int(np.clip(round(score), 0, 5))
    return "★" * filled + "☆" * (5 - filled)


def _score_colour(score: float | None) -> str:
    if score is None:
        return MUTED
    if score >= 3.6:
        return GREEN
    if score <= 1.8:
        return RED
    if score < 2.7:
        return AMBER
    return TEAL_DARK


def _wrapped(text: str, width: int = 58) -> str:
    return "\n".join(textwrap.wrap(str(text), width=width))


def _profile_label(profile: str) -> str:
    return {
        "BANK": "BANKA TEMEL PROFİLİ",
        "GYO": "GYO TEMEL PROFİLİ",
        "GENERIC": "ŞİRKET TEMEL PROFİLİ",
    }.get(profile, "TEMEL PROFİL")


def _radar(fig: plt.Figure, factors: tuple[Factor, ...]) -> None:
    ax = fig.add_axes([0.16, 0.545, 0.68, 0.31], polar=True)
    labels = [factor.name for factor in factors]
    values = [factor.score if factor.score is not None else 0.0 for factor in factors]
    count = len(labels)
    angles = np.linspace(0, 2 * np.pi, count, endpoint=False).tolist()
    angles += angles[:1]
    values += values[:1]

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([_wrapped(label, 17) for label in labels], fontsize=11, color=MUTED)
    ax.grid(color=GRID, linewidth=0.9)
    ax.spines["polar"].set_color(GRID)
    ax.set_facecolor(PANEL)
    ax.plot(angles, values, color=TEAL_DARK, linewidth=2.2)
    ax.fill(angles, values, color=TEAL, alpha=0.45)
    ax.scatter(angles[:-1], values[:-1], s=26, color=TEAL_DARK, zorder=3)


def _factor_rows(fig: plt.Figure, factors: tuple[Factor, ...]) -> None:
    ax = fig.add_axes([0.075, 0.265, 0.85, 0.265])
    ax.axis("off")
    ax.add_patch(
        FancyBboxPatch(
            (0, 0),
            1,
            1,
            boxstyle="round,pad=0.018,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor=PANEL,
            edgecolor=GRID,
            linewidth=1.0,
        )
    )
    top = 0.9
    gap = 0.18
    for index, factor in enumerate(factors):
        y = top - index * gap
        numeric = "—" if factor.score is None else f"{factor.score:.2f}/5"
        ax.text(0.04, y, factor.name, fontsize=13.3, fontweight="bold", color=TEXT, va="center")
        ax.text(0.51, y, numeric, fontsize=13.0, color=_score_colour(factor.score), va="center")
        ax.text(0.96, y, _stars(factor.score), fontsize=15.0, color=TEAL_DARK, va="center", ha="right")
        if factor.detail:
            ax.text(0.04, y - 0.052, factor.detail, fontsize=8.7, color=MUTED, va="top")
        if index < len(factors) - 1:
            ax.plot([0.04, 0.96], [y - 0.085, y - 0.085], color="#edf1f3", linewidth=0.8)


def _insights(fig: plt.Figure, report: FundamentalReport) -> None:
    ax = fig.add_axes([0.075, 0.055, 0.85, 0.19])
    ax.axis("off")
    positives = list(report.positives) or ["Belirgin bir güçlü faktör için veri teyidi yetersiz."]
    risks = list(report.risks) or ["Belirgin bir zayıf faktör saptanmadı; veri kapsamı ayrıca izlenmeli."]

    y = 0.9
    for item in positives[:2]:
        ax.text(0.0, y, "✓", fontsize=14, color=GREEN, fontweight="bold", va="top")
        ax.text(0.04, y, _wrapped(item, 72), fontsize=10.6, color=TEXT, va="top")
        y -= 0.2
    for item in risks[:2]:
        ax.text(0.0, y, "!", fontsize=14, color=RED, fontweight="bold", va="top")
        ax.text(0.04, y, _wrapped(item, 72), fontsize=10.6, color=TEXT, va="top")
        y -= 0.2

    coverage = round(report.coverage * 100)
    footer = f"Veri kapsamı %{coverage} · {report.note}"
    ax.text(0.0, 0.01, _wrapped(footer, 105), fontsize=8.4, color=MUTED, va="bottom")


def render_fundamental_card(report: FundamentalReport, output: Path) -> Path:
    """Render one Telegram-friendly PNG similar to a mobile fundamentals tab."""
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(8.5, 13.2), dpi=140, facecolor=BG)

    company = report.company_name if report.company_name != report.symbol else ""
    price = "—" if report.price is None else f"{report.price:,.2f}"
    score = "—" if report.overall_score is None else f"{report.overall_score:.2f}/5"
    fig.text(0.075, 0.955, f"{report.symbol} · {price}", fontsize=22, fontweight="bold", color=TEXT, va="top")
    if company:
        fig.text(0.075, 0.925, _wrapped(company, 48), fontsize=11.3, color=MUTED, va="top")
    fig.text(0.075, 0.887, _profile_label(report.profile), fontsize=10.5, color=TEAL_DARK, fontweight="bold")

    fig.text(0.075, 0.85, "Genel Skor", fontsize=13.5, color=TEXT, fontweight="bold")
    fig.text(0.59, 0.85, score, fontsize=18, color=_score_colour(report.overall_score), fontweight="bold")
    fig.text(0.92, 0.85, _stars(report.overall_score), fontsize=17, color=TEAL_DARK, ha="right")

    _radar(fig, report.factors)
    _factor_rows(fig, report.factors)
    _insights(fig, report)

    fig.text(
        0.5,
        0.02,
        "Temel durum özeti · otomatik AL/SAT sinyali değildir · yatırım tavsiyesi değildir",
        fontsize=8.2,
        color=MUTED,
        ha="center",
    )
    fig.savefig(output, facecolor=BG, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)
    return output
