"""Integrated technical chart with the user-supplied original indicator logic."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch, Rectangle

from src.original_indicators import DivergencePoint, build_indicator_frame
from src.research_engine import ResearchReport, _prepare_prices

BG = "#070b12"
PANEL = "#0d131d"
PANEL_2 = "#111a27"
GRID = "#273142"
TEXT = "#eef4fb"
MUTED = "#8fa2b8"
GREEN = "#26a69a"
RED = "#ff5252"
AMBER = "#f2bd4a"
BLUE = "#2962ff"
ORANGE = "#ff6d00"
PURPLE = "#7e57c2"
CYAN = "#49d6d0"
MAROON = "#80000b"


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    return f"{value:,.{digits}f}"


def _pct_change(values, periods: int) -> float | None:
    if len(values) <= periods:
        return None
    current = float(values.iloc[-1])
    previous = float(values.iloc[-1 - periods])
    return None if previous == 0 else (current / previous - 1.0) * 100.0


def _badge(ax: plt.Axes, x: float, title: str, value: str, tone: str = MUTED) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, 0.20),
            0.145,
            0.56,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor=PANEL_2,
            edgecolor=GRID,
            linewidth=0.8,
        )
    )
    ax.text(x + 0.015, 0.59, title, transform=ax.transAxes, fontsize=8.0, color=MUTED, va="center")
    ax.text(x + 0.015, 0.36, value, transform=ax.transAxes, fontsize=10.2, color=tone, fontweight="bold", va="center")


def _candles(ax: plt.Axes, data) -> None:
    dates = mdates.date2num(data.index.to_pydatetime())
    width = 0.62
    for date, row in zip(dates, data.itertuples(), strict=False):
        open_price = float(row.Open)
        high = float(row.High)
        low = float(row.Low)
        close = float(row.Close)
        colour = GREEN if close >= open_price else RED
        ax.vlines(date, low, high, linewidth=0.75, color=colour, alpha=0.95, zorder=4)
        bottom = min(open_price, close)
        height = max(abs(close - open_price), max(abs(close) * 0.00045, 1e-6))
        ax.add_patch(
            Rectangle(
                (date - width / 2, bottom),
                width,
                height,
                facecolor=colour,
                edgecolor=colour,
                linewidth=0.55,
                zorder=5,
            )
        )


def _zone_label(zone, kind: str) -> str:
    level = f"{zone.midpoint:,.2f}" if abs(zone.high - zone.low) < 0.005 else f"{zone.low:,.2f}–{zone.high:,.2f}"
    role = "D" if kind == "destek" else "R"
    return f"{role} {level} · Q{zone.score:.0f} · {'+'.join(zone.sources[:3])}"


def _draw_zone(ax: plt.Axes, zone, kind: str, x_start, x_end) -> None:
    colour = GREEN if kind == "destek" else RED
    ax.fill_between([x_start, x_end], [zone.low, zone.low], [zone.high, zone.high], color=colour, alpha=0.10, linewidth=0, zorder=1)
    ax.hlines(zone.midpoint, x_start, x_end, colors=colour, linestyles="--", linewidth=0.8, alpha=0.8, zorder=2)
    ax.annotate(
        _zone_label(zone, kind),
        xy=(x_end, zone.midpoint),
        xytext=(7, 0),
        textcoords="offset points",
        fontsize=7.4,
        color=colour,
        va="center",
        ha="left",
        bbox={"boxstyle": "round,pad=0.20", "fc": PANEL_2, "ec": colour, "lw": 0.5, "alpha": 0.94},
        annotation_clip=False,
    )


def _style_panel(ax: plt.Axes, *, right_axis: bool = False) -> None:
    ax.set_facecolor(PANEL)
    ax.grid(True, color=GRID, alpha=0.34, linewidth=0.5)
    ax.tick_params(colors=MUTED, labelsize=7.1)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    if right_axis:
        ax.yaxis.tick_right()
        ax.tick_params(axis="y", labelleft=False, labelright=True)


def _panel_label(ax: plt.Axes, text: str) -> None:
    ax.text(0.006, 0.86, text, transform=ax.transAxes, fontsize=7.8, fontweight="bold", color=TEXT, va="top")


def _draw_rsi_divergences(ax: plt.Axes, points: tuple[DivergencePoint, ...], start, end) -> None:
    for point in points:
        if point.index < start or point.index > end:
            continue
        bullish = "Bullish" in point.kind
        colour = GREEN if bullish else RED
        text = "Bull" if point.kind == "Regular Bullish" else "Bear" if point.kind == "Regular Bearish" else "H Bull" if bullish else "H Bear"
        ax.scatter([point.index], [point.rsi], s=22, color=colour, zorder=8)
        ax.annotate(
            text,
            xy=(point.index, point.rsi),
            xytext=(0, -14 if bullish else 14),
            textcoords="offset points",
            fontsize=6.5,
            color=TEXT,
            ha="center",
            va="center",
            bbox={"boxstyle": "round,pad=0.18", "fc": colour, "ec": colour, "lw": 0.4, "alpha": 0.88},
        )


def render_research_chart(symbol: str, report: ResearchReport, output: Path) -> Path:
    """Render price + volume + MACD + SMI + RSI/divergence + OBV + ATR."""
    import borsapy as bp

    output.parent.mkdir(parents=True, exist_ok=True)
    raw = _prepare_prices(bp.Ticker(symbol).history(period="2y", interval="1d"))
    data, divergences = build_indicator_frame(raw, include_hidden_divergence=False)
    view = data.tail(150).copy()
    if view.empty:
        raise RuntimeError("No price bars available for research chart")

    plt.rcParams["font.family"] = "DejaVu Sans"
    figure = plt.figure(figsize=(15.5, 18.5), dpi=135, facecolor=BG)
    grid = figure.add_gridspec(
        8,
        1,
        height_ratios=[1.05, 5.0, 1.05, 1.45, 1.45, 1.45, 1.25, 1.15],
        hspace=0.045,
    )
    header_ax = figure.add_subplot(grid[0])
    price_ax = figure.add_subplot(grid[1])
    volume_ax = figure.add_subplot(grid[2], sharex=price_ax)
    macd_ax = figure.add_subplot(grid[3], sharex=price_ax)
    smi_ax = figure.add_subplot(grid[4], sharex=price_ax)
    rsi_ax = figure.add_subplot(grid[5], sharex=price_ax)
    obv_ax = figure.add_subplot(grid[6], sharex=price_ax)
    atr_ax = figure.add_subplot(grid[7], sharex=price_ax)

    header_ax.set_facecolor(PANEL)
    header_ax.axis("off")
    for current in (price_ax, volume_ax, macd_ax, smi_ax, rsi_ax, obv_ax, atr_ax):
        _style_panel(current, right_axis=True)

    price = float(view["Close"].iloc[-1])
    day = _pct_change(view["Close"], 1)
    week = _pct_change(view["Close"], 5)
    month = _pct_change(view["Close"], 21)
    structure = report.technical.get("structure", {})
    weekly = report.technical.get("weekly_structure", {})
    technical_score = report.technical.get("score")

    header_ax.text(0.018, 0.74, report.symbol, transform=header_ax.transAxes, fontsize=22, color=TEXT, fontweight="bold", va="center")
    header_ax.text(0.018, 0.39, f"{price:,.2f} TL", transform=header_ax.transAxes, fontsize=18, color=CYAN, fontweight="bold", va="center")
    header_ax.text(0.018, 0.10, f"Günlük {structure.get('state', '—')} · Haftalık {weekly.get('state', '—')} · {structure.get('bos', 'Yeni BOS yok')}", transform=header_ax.transAxes, fontsize=8.5, color=MUTED, va="center")
    _badge(header_ax, 0.26, "1 GÜN", "—" if day is None else f"{day:+.2f}%", GREEN if day is not None and day >= 0 else RED)
    _badge(header_ax, 0.42, "1 HAFTA", "—" if week is None else f"{week:+.2f}%", GREEN if week is not None and week >= 0 else RED)
    _badge(header_ax, 0.58, "1 AY", "—" if month is None else f"{month:+.2f}%", GREEN if month is not None and month >= 0 else RED)
    score_tone = GREEN if technical_score is not None and technical_score >= 70 else AMBER if technical_score is not None and technical_score >= 45 else RED
    _badge(header_ax, 0.74, "TEKNİK YAPI", "—" if technical_score is None else f"{technical_score:.0f}/100", score_tone)

    _candles(price_ax, view)
    price_ax.plot(view.index, view["BB_MID"], color="#aeb7c4", linewidth=0.75, alpha=0.75, label="BB Basis 20")
    price_ax.plot(view.index, view["BB_UPPER"], color="#6b7280", linewidth=0.65, alpha=0.75)
    price_ax.plot(view.index, view["BB_LOWER"], color="#6b7280", linewidth=0.65, alpha=0.75)
    price_ax.fill_between(view.index, view["BB_LOWER"].to_numpy(), view["BB_UPPER"].to_numpy(), color="#64748b", alpha=0.055, zorder=0)

    alpha = view["AlphaTrend"]
    alpha_lag2 = view["AlphaTrendLag2"]
    price_ax.plot(view.index, alpha, color=BLUE, linewidth=1.4, label="AlphaTrend")
    price_ax.plot(view.index, alpha_lag2, color=RED, linewidth=1.1, alpha=0.9, label="AlphaTrend[2]")
    valid_alpha = alpha.notna() & alpha_lag2.notna()
    price_ax.fill_between(
        view.index,
        alpha.to_numpy(),
        alpha_lag2.to_numpy(),
        where=(alpha >= alpha_lag2).fillna(False).to_numpy() & valid_alpha.to_numpy(),
        color="#00e60f",
        alpha=0.12,
        interpolate=True,
    )
    price_ax.fill_between(
        view.index,
        alpha.to_numpy(),
        alpha_lag2.to_numpy(),
        where=(alpha < alpha_lag2).fillna(False).to_numpy() & valid_alpha.to_numpy(),
        color=MAROON,
        alpha=0.16,
        interpolate=True,
    )

    x_start = mdates.date2num(view.index[0].to_pydatetime())
    x_end = mdates.date2num(view.index[-1].to_pydatetime())
    for zone in report.supports:
        _draw_zone(price_ax, zone, "destek", x_start, x_end)
    for zone in report.resistances:
        _draw_zone(price_ax, zone, "direnç", x_start, x_end)

    y_min = float(view["Low"].min())
    y_max = float(view["High"].max())
    span = max(y_max - y_min, 1e-6)
    for pivot in [item for item in report.technical.get("pivots", []) if item.get("time")][-11:]:
        try:
            time = np.datetime64(str(pivot["time"]))
        except ValueError:
            continue
        if time < np.datetime64(view.index[0]):
            continue
        pivot_price = float(pivot["price"])
        offset = span * (0.024 if pivot["type"] == "high" else -0.030)
        price_ax.text(time, pivot_price + offset, str(pivot["label"]), fontsize=7.3, fontweight="bold", color=TEXT, ha="center", va="center", bbox={"boxstyle": "round,pad=0.12", "fc": PANEL_2, "ec": GRID, "lw": 0.4, "alpha": 0.86}, zorder=8)

    bos = str(structure.get("bos", ""))
    if "BOS" in bos:
        level = None
        if "High" in bos and structure.get("last_high"):
            level = float(structure["last_high"]["price"])
        elif "Low" in bos and structure.get("last_low"):
            level = float(structure["last_low"]["price"])
        if level is not None:
            price_ax.axhline(level, linestyle=(0, (4, 4)), linewidth=0.9, color=AMBER, alpha=0.85)
            price_ax.text(view.index[int(len(view) * 0.58)], level, f" BOS · {level:,.2f}", fontsize=7.8, color=AMBER, va="bottom", bbox={"boxstyle": "round,pad=0.16", "fc": PANEL_2, "ec": AMBER, "lw": 0.4, "alpha": 0.90})

    price_ax.axhline(price, linewidth=0.7, color=CYAN, alpha=0.35)
    price_ax.annotate(f" {price:,.2f}", xy=(x_end, price), xytext=(7, 0), textcoords="offset points", fontsize=8.0, color=TEXT, va="center", ha="left", bbox={"boxstyle": "round,pad=0.20", "fc": CYAN, "ec": CYAN, "lw": 0.5, "alpha": 0.82}, annotation_clip=False)
    price_ax.legend(loc="upper left", ncol=3, fontsize=7.4, frameon=False, labelcolor=TEXT)
    price_ax.set_xlim(view.index[0], view.index[-1] + np.timedelta64(12, "D"))
    _panel_label(price_ax, "FİYAT · BOLLINGER(20,2) · ALPHATREND(14,1)")

    volume_colours = [GREEN if close >= open_price else RED for open_price, close in zip(view["Open"], view["Close"], strict=False)]
    volume_ax.bar(view.index, view["Volume"], width=0.82, alpha=0.60, color=volume_colours)
    volume_avg = view["Volume"].rolling(20).mean()
    volume_ax.plot(view.index, volume_avg, color=AMBER, linewidth=0.8, alpha=0.9)
    _panel_label(volume_ax, "HACİM · 20G ORT.")

    hist = view["MACD_HIST"]
    hist_prev = hist.shift(1)
    hist_colours = np.where(hist >= 0, np.where(hist > hist_prev, "#26a69a", "#b2dfdb"), np.where(hist > hist_prev, "#ffcdd2", "#ff5252"))
    macd_ax.bar(view.index, hist, width=0.82, color=hist_colours, alpha=0.85)
    macd_ax.plot(view.index, view["MACD"], color=BLUE, linewidth=1.0)
    macd_ax.plot(view.index, view["MACD_SIGNAL"], color=ORANGE, linewidth=1.0)
    macd_ax.axhline(0, color=MUTED, linewidth=0.65, alpha=0.7)
    _panel_label(macd_ax, "MACD · 12/26/9 EMA")

    smi_ax.plot(view.index, view["SMI"], color=BLUE, linewidth=1.0)
    smi_ax.plot(view.index, view["SMI_SIGNAL"], color=ORANGE, linewidth=1.0)
    smi_ax.axhline(40, color=MUTED, linewidth=0.6)
    smi_ax.axhline(-40, color=MUTED, linewidth=0.6)
    smi_ax.axhline(0, color=MUTED, linewidth=0.5, alpha=0.55)
    smi_ax.fill_between(view.index, -40, 40, color=BLUE, alpha=0.055)
    smi_ax.set_ylim(-120, 120)
    _panel_label(smi_ax, "SMI · 10/3/3")

    rsi_ax.plot(view.index, view["RSI14"], color=PURPLE, linewidth=1.15)
    rsi_ax.axhline(70, color=MUTED, linewidth=0.6)
    rsi_ax.axhline(50, color=MUTED, linewidth=0.55, linestyle=":")
    rsi_ax.axhline(30, color=MUTED, linewidth=0.6)
    rsi_ax.fill_between(view.index, 30, 70, color=PURPLE, alpha=0.055)
    rsi_ax.set_ylim(0, 100)
    _draw_rsi_divergences(rsi_ax, divergences, view.index[0], view.index[-1])
    _panel_label(rsi_ax, "RSI · 14 · REGULAR DIVERGENCE AÇIK (5/5, 5–60)")

    obv_ax.plot(view.index, view["OBV"], color=BLUE, linewidth=1.05)
    _panel_label(obv_ax, "OBV · ORİJİNAL KÜMÜLATİF")

    atr_ax.plot(view.index, view["ATR14"], color="#b71c1c", linewidth=1.05)
    _panel_label(atr_ax, "ATR · 14 RMA")
    atr_ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=7, maxticks=11))
    atr_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))

    for current in (price_ax, volume_ax, macd_ax, smi_ax, rsi_ax, obv_ax):
        plt.setp(current.get_xticklabels(), visible=False)

    figure.text(0.015, 0.009, "Gösterge mantığı: kullanıcı tarafından sağlanan TradingView/Pine kodları · AlphaTrend BUY/SELL etiketleri raporda bastırılır", fontsize=7.3, color=MUTED, ha="left")
    figure.text(0.985, 0.009, "MA 5/8/13 · 21/34/55 · 89/144/233 ayrı tabloda · otomatik AL/SAT değildir", fontsize=7.3, color=MUTED, ha="right")
    figure.savefig(output, facecolor=BG, bbox_inches="tight", pad_inches=0.15)
    plt.close(figure)
    return output
