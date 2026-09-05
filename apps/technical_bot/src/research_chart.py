"""Professional technical structure chart for the integrated research report.

The visual language is intentionally compact and broker-terminal-like: dark
background, one-glance header, candlesticks + volume, shaded actionable zones,
market-structure labels and a small diagnostics strip. It is not a copy of any
third-party chart and only renders information produced by our own engine.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle

from src.research_engine import ResearchReport, _prepare_prices

BG = "#0b1220"
PANEL = "#111a2b"
PANEL_2 = "#0f1928"
GRID = "#223047"
TEXT = "#eef4fb"
MUTED = "#8fa2b8"
GREEN = "#39c98a"
RED = "#ff6577"
AMBER = "#f2bd4a"
BLUE = "#5aa9ff"
PURPLE = "#a987ff"
CYAN = "#49d6d0"


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}"


def _pct_change(values, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    current = float(values.iloc[-1])
    previous = float(values.iloc[-1 - periods])
    if previous == 0:
        return None
    return (current / previous - 1.0) * 100.0


def _badge(ax: plt.Axes, x: float, y: float, title: str, value: str, tone: str = MUTED) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            0.145,
            0.56,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor=PANEL_2,
            edgecolor=GRID,
            linewidth=0.8,
        )
    )
    ax.text(x + 0.015, y + 0.39, title, transform=ax.transAxes, fontsize=8.2, color=MUTED, va="center")
    ax.text(x + 0.015, y + 0.16, value, transform=ax.transAxes, fontsize=10.5, color=tone, fontweight="bold", va="center")


def _candles(ax: plt.Axes, data) -> None:
    dates = mdates.date2num(data.index.to_pydatetime())
    width = 0.62
    for date, row in zip(dates, data.itertuples(), strict=False):
        open_price = float(row.Open)
        high = float(row.High)
        low = float(row.Low)
        close = float(row.Close)
        colour = GREEN if close >= open_price else RED
        ax.vlines(date, low, high, linewidth=0.78, color=colour, alpha=0.95, zorder=3)
        bottom = min(open_price, close)
        height = max(abs(close - open_price), max(abs(close) * 0.00045, 1e-6))
        ax.add_patch(
            Rectangle(
                (date - width / 2, bottom),
                width,
                height,
                facecolor=colour,
                edgecolor=colour,
                linewidth=0.6,
                zorder=4,
            )
        )


def _zone_label(zone, kind: str) -> str:
    if abs(zone.high - zone.low) < 0.005:
        level = f"{zone.midpoint:,.2f}"
    else:
        level = f"{zone.low:,.2f}–{zone.high:,.2f}"
    role = "D" if kind == "destek" else "R"
    source = "+".join(zone.sources[:3])
    return f"{role} {level} · Q{zone.score:.0f} · {source}"


def _draw_zone(ax: plt.Axes, zone, kind: str, x_start, x_end) -> None:
    colour = GREEN if kind == "destek" else RED
    ax.fill_between(
        [x_start, x_end],
        [zone.low, zone.low],
        [zone.high, zone.high],
        color=colour,
        alpha=0.105,
        linewidth=0,
        zorder=1,
    )
    ax.hlines(zone.midpoint, x_start, x_end, colors=colour, linestyles="--", linewidth=0.85, alpha=0.8, zorder=2)
    ax.annotate(
        _zone_label(zone, kind),
        xy=(x_end, zone.midpoint),
        xytext=(7, 0),
        textcoords="offset points",
        fontsize=7.8,
        color=colour,
        va="center",
        ha="left",
        bbox={"boxstyle": "round,pad=0.22", "fc": PANEL_2, "ec": colour, "lw": 0.55, "alpha": 0.94},
        annotation_clip=False,
    )


def render_research_chart(symbol: str, report: ResearchReport, output: Path) -> Path:
    """Render a dark, information-dense research chart without stale levels."""
    import borsapy as bp

    output.parent.mkdir(parents=True, exist_ok=True)
    data = _prepare_prices(bp.Ticker(symbol).history(period="2y", interval="1d")).dropna(subset=["ATR"])
    view = data.tail(130).copy()
    if view.empty:
        raise RuntimeError("No price bars available for research chart")

    plt.rcParams["font.family"] = "DejaVu Sans"
    figure = plt.figure(figsize=(15.5, 10.0), dpi=135, facecolor=BG)
    grid = figure.add_gridspec(3, 1, height_ratios=[1.15, 5.0, 1.25], hspace=0.03)
    header_ax = figure.add_subplot(grid[0])
    ax = figure.add_subplot(grid[1])
    volume_ax = figure.add_subplot(grid[2], sharex=ax)

    for current_ax in (header_ax, ax, volume_ax):
        current_ax.set_facecolor(PANEL)
    header_ax.axis("off")

    price = float(view["Close"].iloc[-1])
    day = _pct_change(view["Close"], 1)
    week = _pct_change(view["Close"], 5)
    month = _pct_change(view["Close"], 21)
    structure = report.technical.get("structure", {})
    weekly = report.technical.get("weekly_structure", {})

    header_ax.text(0.02, 0.77, report.symbol, transform=header_ax.transAxes, fontsize=22, color=TEXT, fontweight="bold", va="center")
    header_ax.text(0.02, 0.43, f"{price:,.2f} TL", transform=header_ax.transAxes, fontsize=18, color=CYAN, fontweight="bold", va="center")
    header_ax.text(
        0.02,
        0.13,
        f"Günlük {structure.get('state', '—')} · Haftalık {weekly.get('state', '—')} · {structure.get('bos', 'Yeni BOS yok')}",
        transform=header_ax.transAxes,
        fontsize=8.8,
        color=MUTED,
        va="center",
    )

    _badge(header_ax, 0.26, 0.20, "1 GÜN", "—" if day is None else f"{day:+.2f}%", GREEN if day is not None and day >= 0 else RED)
    _badge(header_ax, 0.42, 0.20, "1 HAFTA", "—" if week is None else f"{week:+.2f}%", GREEN if week is not None and week >= 0 else RED)
    _badge(header_ax, 0.58, 0.20, "1 AY", "—" if month is None else f"{month:+.2f}%", GREEN if month is not None and month >= 0 else RED)
    technical_score = report.technical.get("score")
    _badge(
        header_ax,
        0.74,
        0.20,
        "TEKNİK YAPI",
        "—" if technical_score is None else f"{technical_score:.0f}/100",
        GREEN if technical_score is not None and technical_score >= 70 else AMBER if technical_score is not None and technical_score >= 45 else RED,
    )

    _candles(ax, view)
    ema_styles = (
        (21, "EMA21", BLUE, 1.35),
        (55, "EMA55", PURPLE, 1.25),
        (233, "EMA233", AMBER, 1.05),
    )
    for period, label, colour, width in ema_styles:
        column = f"EMA_{period}"
        if column in view and view[column].notna().any():
            ax.plot(view.index, view[column], linewidth=width, color=colour, label=label, alpha=0.95, zorder=5)

    x_start = mdates.date2num(view.index[0].to_pydatetime())
    x_end = mdates.date2num(view.index[-1].to_pydatetime())
    for zone in report.supports:
        _draw_zone(ax, zone, "destek", x_start, x_end)
    for zone in report.resistances:
        _draw_zone(ax, zone, "direnç", x_start, x_end)

    y_min = float(view["Low"].min())
    y_max = float(view["High"].max())
    span = max(y_max - y_min, 1e-6)
    first_index = view.index[0]
    pivots = [item for item in report.technical.get("pivots", []) if item.get("time")]
    for pivot in pivots[-11:]:
        try:
            time = np.datetime64(str(pivot["time"]))
        except ValueError:
            continue
        if time < np.datetime64(first_index):
            continue
        pivot_price = float(pivot["price"])
        label = str(pivot["label"])
        offset = span * (0.024 if pivot["type"] == "high" else -0.030)
        ax.text(
            time,
            pivot_price + offset,
            label,
            fontsize=7.8,
            fontweight="bold",
            color=TEXT,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.14", "fc": PANEL_2, "ec": GRID, "lw": 0.45, "alpha": 0.88},
            zorder=7,
        )

    bos = str(structure.get("bos", ""))
    if "BOS" in bos:
        level = None
        if "High" in bos and structure.get("last_high"):
            level = float(structure["last_high"]["price"])
        elif "Low" in bos and structure.get("last_low"):
            level = float(structure["last_low"]["price"])
        if level is not None:
            ax.axhline(level, linestyle=(0, (4, 4)), linewidth=0.95, color=AMBER, alpha=0.85, zorder=2)
            ax.text(
                view.index[int(len(view) * 0.58)],
                level,
                f" BOS · {level:,.2f}",
                fontsize=8.3,
                color=AMBER,
                va="bottom",
                ha="left",
                bbox={"boxstyle": "round,pad=0.18", "fc": PANEL_2, "ec": AMBER, "lw": 0.45, "alpha": 0.90},
            )

    ax.axhline(price, linewidth=0.75, color=CYAN, alpha=0.40, zorder=1)
    ax.annotate(
        f" {price:,.2f}",
        xy=(x_end, price),
        xytext=(7, 0),
        textcoords="offset points",
        fontsize=8.5,
        color=TEXT,
        va="center",
        ha="left",
        bbox={"boxstyle": "round,pad=0.22", "fc": CYAN, "ec": CYAN, "lw": 0.6, "alpha": 0.85},
        annotation_clip=False,
    )

    ax.legend(loc="upper left", ncol=3, fontsize=8.2, frameon=False, labelcolor=TEXT)
    ax.grid(True, color=GRID, alpha=0.33, linewidth=0.55)
    ax.tick_params(colors=MUTED, labelsize=8.0, axis="y", labelleft=False, labelright=True)
    ax.yaxis.tick_right()
    ax.set_xlim(view.index[0], view.index[-1] + np.timedelta64(12, "D"))
    for spine in ax.spines.values():
        spine.set_color(GRID)
    plt.setp(ax.get_xticklabels(), visible=False)

    volume_colours = [GREEN if close >= open_price else RED for open_price, close in zip(view["Open"], view["Close"], strict=False)]
    volume_ax.bar(view.index, view["Volume"], width=0.82, alpha=0.52, color=volume_colours)
    volume_ax.grid(True, color=GRID, alpha=0.28, linewidth=0.5)
    volume_ax.tick_params(colors=MUTED, labelsize=7.8)
    volume_ax.tick_params(axis="y", labelleft=False)
    for spine in volume_ax.spines.values():
        spine.set_color(GRID)
    volume_ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=7, maxticks=11))
    volume_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

    diagnostics = (
        f"RSI14  {_fmt(report.technical.get('rsi14'), 1)}    "
        f"ATR  %{_fmt(report.technical.get('atr_pct'), 1)}    "
        f"RVOL20  {_fmt(report.technical.get('rvol20'), 2)}x    "
        f"EMA21  {_fmt(report.technical.get('ema21'))}    "
        f"EMA55  {_fmt(report.technical.get('ema55'))}    "
        f"EMA233  {_fmt(report.technical.get('ema233'))}"
    )
    volume_ax.text(
        0.012,
        0.91,
        diagnostics,
        transform=volume_ax.transAxes,
        fontsize=8.4,
        color=TEXT,
        va="top",
        bbox={"boxstyle": "round,pad=0.34", "fc": PANEL_2, "ec": GRID, "lw": 0.55, "alpha": 0.93},
    )

    figure.text(
        0.015,
        0.012,
        "Aktif seviye motoru: pivot + EMA + Fibonacci + POC + temas/reaksiyon + ATR mesafesi",
        fontsize=7.7,
        color=MUTED,
        ha="left",
    )
    figure.text(
        0.985,
        0.012,
        "Uzak/eski seviyeler aksiyon seviyesi olarak çizilmez · otomatik AL/SAT değildir",
        fontsize=7.7,
        color=MUTED,
        ha="right",
    )
    figure.savefig(output, facecolor=BG, bbox_inches="tight", pad_inches=0.16)
    plt.close(figure)
    return output
