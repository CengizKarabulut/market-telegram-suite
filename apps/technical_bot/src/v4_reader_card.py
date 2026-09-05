from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

CARD_WIDTH = 10.8
CARD_HEIGHT = 15.8
CARD_DPI = 100


def _text(value: Any, fallback: str = "—") -> str:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or fallback


def _wrap(value: Any, width: int) -> str:
    return "\n".join(
        textwrap.wrap(
            _text(value),
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
    )


def _price(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"%{float(value):+.2f}"
    except (TypeError, ValueError):
        return "—"


def _box(ax, x: float, y: float, w: float, h: float, title: str) -> None:
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.0,
        edgecolor="#26354d",
        facecolor="#111a28",
        transform=ax.transAxes,
    )
    ax.add_patch(patch)
    ax.text(
        x + 0.022,
        y + h - 0.025,
        title,
        transform=ax.transAxes,
        fontsize=10.7,
        fontweight="bold",
        color="#9fb5d8",
        va="top",
    )


def _body(ax, x: float, y: float, text: Any, width: int, size: float = 9.7) -> None:
    ax.text(
        x,
        y,
        _wrap(text, width),
        fontsize=size,
        color="#e4ebf5",
        va="top",
        linespacing=1.42,
        transform=ax.transAxes,
    )


def render_reader_card(report: dict[str, Any], output_path: Path) -> Path:
    """Teknik kodları ve tarama marka/adlarını gizleyen son kullanıcı analiz kartı."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(
        figsize=(CARD_WIDTH, CARD_HEIGHT),
        dpi=CARD_DPI,
        facecolor="#08111f",
    )
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_facecolor("#08111f")

    reader = report.get("reader_view") or {}
    symbol = _text(report.get("symbol"))
    interval = _text(report.get("interval_label"), _text(report.get("interval")))

    ax.text(
        0.055,
        0.963,
        f"{symbol} · ANALİST GÖRÜŞÜ",
        fontsize=22,
        fontweight="bold",
        color="#f5f8ff",
        va="top",
    )
    ax.text(
        0.055,
        0.936,
        f"{interval} görünüm",
        fontsize=10.5,
        color="#8ea1bf",
        va="top",
    )
    ax.text(
        0.945,
        0.963,
        _price(report.get("price")),
        fontsize=24,
        fontweight="bold",
        color="#f5f8ff",
        ha="right",
        va="top",
    )
    ax.text(
        0.945,
        0.936,
        _pct(report.get("change_pct")),
        fontsize=11.5,
        color="#c1ccdd",
        ha="right",
        va="top",
    )

    ax.text(
        0.055,
        0.892,
        _wrap(reader.get("headline"), 84),
        fontsize=14.2,
        fontweight="bold",
        color="#d9e5f7",
        va="top",
        linespacing=1.30,
    )

    _box(ax, 0.045, 0.748, 0.91, 0.115, "GENEL GÖRÜNÜM")
    _body(ax, 0.068, 0.815, reader.get("overview"), 105, 10.0)

    _box(ax, 0.045, 0.605, 0.44, 0.115, "KISA VADEDE GÜÇ")
    _body(ax, 0.068, 0.672, reader.get("momentum"), 48, 9.4)

    _box(ax, 0.515, 0.605, 0.44, 0.115, "HAREKETİN ARKASINDA PARA VAR MI?")
    _body(ax, 0.538, 0.672, reader.get("participation"), 48, 9.4)

    _box(ax, 0.045, 0.465, 0.44, 0.11, "EK TEKNİK KOŞULLAR")
    _body(ax, 0.068, 0.528, reader.get("screening"), 48, 9.2)

    _box(ax, 0.515, 0.465, 0.44, 0.11, "ÖNEMLİ FİYAT BÖLGELERİ")
    _body(ax, 0.538, 0.528, reader.get("levels"), 48, 9.2)

    _box(ax, 0.045, 0.325, 0.91, 0.11, "SON SEANSTA NE DEĞİŞTİ?")
    _body(ax, 0.068, 0.388, reader.get("what_changed"), 105, 9.7)

    _box(ax, 0.045, 0.135, 0.91, 0.16, "ANALİST SONUCU")
    _body(ax, 0.068, 0.252, reader.get("conclusion"), 108, 10.2)

    ax.text(
        0.055,
        0.058,
        "Durum analizi ve senaryo çerçevesidir; otomatik alım/satım emri değildir.",
        fontsize=8.8,
        color="#71839e",
        va="bottom",
    )
    ax.text(
        0.945,
        0.058,
        _text(report.get("timestamp")),
        fontsize=8.8,
        color="#71839e",
        ha="right",
        va="bottom",
    )

    fig.savefig(
        output_path,
        dpi=CARD_DPI,
        facecolor=fig.get_facecolor(),
        bbox_inches=None,
    )
    plt.close(fig)
    return output_path
