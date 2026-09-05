"""Technical structure chart used by the integrated research report."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from src.research_engine import ResearchReport, _prepare_prices


def _candles(ax: plt.Axes, data) -> None:
    dates = mdates.date2num(data.index.to_pydatetime())
    width = 0.62
    for date, row in zip(dates, data.itertuples(), strict=False):
        open_price = float(row.Open)
        high = float(row.High)
        low = float(row.Low)
        close = float(row.Close)
        positive = close >= open_price
        colour = "#2e9f6b" if positive else "#d9534f"
        ax.vlines(date, low, high, linewidth=0.8, color=colour, alpha=0.95)
        bottom = min(open_price, close)
        height = max(abs(close - open_price), max(abs(close) * 0.0005, 1e-6))
        ax.add_patch(Rectangle((date - width / 2, bottom), width, height, facecolor=colour, edgecolor=colour, linewidth=0.7))


def render_research_chart(symbol: str, report: ResearchReport, output: Path) -> Path:
    import borsapy as bp

    output.parent.mkdir(parents=True, exist_ok=True)
    data = _prepare_prices(bp.Ticker(symbol).history(period="2y", interval="1d")).dropna(subset=["ATR"])
    view = data.tail(125).copy()
    if view.empty:
        raise RuntimeError("No price bars available for research chart")

    plt.rcParams["font.family"] = "DejaVu Sans"
    figure, (ax, volume_ax) = plt.subplots(
        2,
        1,
        figsize=(14, 8.8),
        dpi=130,
        sharex=True,
        gridspec_kw={"height_ratios": [4.3, 1.0], "hspace": 0.05},
    )
    figure.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#111827")
    volume_ax.set_facecolor("#111827")

    _candles(ax, view)
    for period, label in ((21, "EMA21"), (55, "EMA55"), (233, "EMA233")):
        column = f"EMA_{period}"
        if column in view and view[column].notna().any():
            ax.plot(view.index, view[column], linewidth=1.2, label=label)

    y_min = float(view["Low"].min())
    y_max = float(view["High"].max())
    span = max(y_max - y_min, 1e-6)

    for zone in report.supports:
        ax.axhspan(zone.low, zone.high, alpha=0.12)
        ax.text(
            view.index[-1],
            zone.midpoint,
            f" DESTEK {zone.low:,.2f}–{zone.high:,.2f} · {zone.score:.0f}",
            fontsize=8.2,
            color="#86efac",
            va="center",
            ha="left",
        )
    for zone in report.resistances:
        ax.axhspan(zone.low, zone.high, alpha=0.12)
        ax.text(
            view.index[-1],
            zone.midpoint,
            f" DİRENÇ {zone.low:,.2f}–{zone.high:,.2f} · {zone.score:.0f}",
            fontsize=8.2,
            color="#fca5a5",
            va="center",
            ha="left",
        )

    first_index = view.index[0]
    pivots = [item for item in report.technical.get("pivots", []) if item.get("time")]
    for pivot in pivots[-10:]:
        try:
            time = np.datetime64(str(pivot["time"]))
        except ValueError:
            continue
        if time < np.datetime64(first_index):
            continue
        price = float(pivot["price"])
        label = str(pivot["label"])
        offset = span * (0.018 if pivot["type"] == "high" else -0.025)
        ax.text(
            time,
            price + offset,
            label,
            fontsize=8.5,
            fontweight="bold",
            color="#e2e8f0",
            ha="center",
            va="center",
        )

    structure = report.technical.get("structure", {})
    bos = str(structure.get("bos", ""))
    if "BOS" in bos:
        level = None
        if "High" in bos and structure.get("last_high"):
            level = float(structure["last_high"]["price"])
        elif "Low" in bos and structure.get("last_low"):
            level = float(structure["last_low"]["price"])
        if level is not None:
            ax.axhline(level, linestyle="--", linewidth=1.0, alpha=0.8)
            ax.text(view.index[int(len(view) * 0.55)], level, f" BOS · {level:,.2f}", fontsize=9, color="#facc15", va="bottom")

    ax.set_title(
        f"{report.symbol} · Teknik Yapı | {structure.get('state', '—')} | {report.technical.get('label', '—')}",
        fontsize=15,
        color="#f8fafc",
        loc="left",
        pad=12,
        fontweight="bold",
    )
    subtitle = (
        f"Günlük + haftalık bağlam · RSI {report.technical.get('rsi14', float('nan')):.1f} · "
        f"ATR %{report.technical.get('atr_pct', float('nan')):.1f} · "
        f"RVOL {report.technical.get('rvol20', float('nan')):.2f}x"
    )
    ax.text(0.0, 1.01, subtitle, transform=ax.transAxes, color="#94a3b8", fontsize=9.3, va="bottom")
    ax.legend(loc="upper left", ncol=3, fontsize=8.5, frameon=False, labelcolor="#e2e8f0")
    ax.grid(alpha=0.12)
    ax.tick_params(colors="#cbd5e1", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#334155")

    volume_colours = ["#2e9f6b" if close >= open_price else "#d9534f" for open_price, close in zip(view["Open"], view["Close"], strict=False)]
    volume_ax.bar(view.index, view["Volume"], width=0.8, alpha=0.65, color=volume_colours)
    volume_ax.set_ylabel("Hacim", color="#94a3b8", fontsize=8.5)
    volume_ax.grid(alpha=0.10)
    volume_ax.tick_params(colors="#cbd5e1", labelsize=8)
    for spine in volume_ax.spines.values():
        spine.set_color("#334155")
    volume_ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=10))
    volume_ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

    figure.text(
        0.99,
        0.012,
        "Yalnız aktif/yakın seviyeler · uzak/eski seviyeler aksiyon seviyesi olarak çizilmez · yatırım tavsiyesi değildir",
        ha="right",
        fontsize=7.8,
        color="#94a3b8",
    )
    figure.savefig(output, facecolor=figure.get_facecolor(), bbox_inches="tight", pad_inches=0.16)
    plt.close(figure)
    return output
