from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

CARD_WIDTH = 10.8
CARD_HEIGHT = 13.5
CARD_DPI = 100


def _text(value: Any, fallback: str = "—") -> str:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or fallback


def _wrap(value: Any, width: int) -> str:
    return "\n".join(textwrap.wrap(_text(value), width=width, break_long_words=False, break_on_hyphens=False))


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
        y + h - 0.035,
        title,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        color="#9fb5d8",
        va="top",
    )


def _level_line(level: dict[str, Any] | None, prefix: str) -> str:
    if not level:
        return f"{prefix}: yakın aktif referans yok"
    return f"{prefix}: {_price(level.get('value'))} · {_text(level.get('role'))} · {_text(level.get('class'))}"


def _scenario_lines(report: dict[str, Any]) -> list[str]:
    scenarios = report.get("scenarios", {}) or {}
    result: list[str] = []
    for label, key in (("Yukarı", "up"), ("Aşağı", "down")):
        items = list(scenarios.get(key) or [])
        if not items:
            continue
        result.append(f"{label}: {_text(items[0].get('confirmation_rule'))}")
    return result or ["Yakın vadede bekleyen doğrulanmış senaryo seviyesi yok."]


def _structural_lines(report: dict[str, Any]) -> list[str]:
    levels = list(report.get("structural_levels") or [])
    if not levels:
        return ["Uzak yapısal referans yok."]
    lines: list[str] = []
    for level in levels[:3]:
        lines.append(
            f"{_price(level.get('value'))} · {_text(level.get('role'))} · {_text(level.get('lifecycle'))}"
        )
    return lines


def render_v3_card(report: dict[str, Any], output_path: Path) -> Path:
    """V3 report contract'tan tek sayfalık, business-logic içermeyen kart üretir."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(CARD_WIDTH, CARD_HEIGHT), dpi=CARD_DPI, facecolor="#08111f")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_facecolor("#08111f")

    symbol = _text(report.get("symbol"))
    interval = _text(report.get("interval_label"), _text(report.get("interval")))
    ax.text(0.055, 0.955, f"{symbol} · V3 MARKET STATE", fontsize=22, fontweight="bold", color="#f5f8ff", va="top")
    ax.text(0.055, 0.918, f"{interval} teknik durum", fontsize=11, color="#8ea1bf", va="top")
    ax.text(0.945, 0.955, _price(report.get("price")), fontsize=24, fontweight="bold", color="#f5f8ff", ha="right", va="top")
    ax.text(0.945, 0.918, _pct(report.get("change_pct")), fontsize=12, color="#c1ccdd", ha="right", va="top")

    headline = _wrap(report.get("headline"), 78)
    ax.text(0.055, 0.862, headline, fontsize=14, fontweight="bold", color="#d9e5f7", va="top", linespacing=1.35)

    _box(ax, 0.045, 0.642, 0.91, 0.175, "PIYASA DURUMU")
    current = report.get("current_state", {}) or {}
    state_lines = [
        f"Yapı: {_text(current.get('structure'))}",
        f"Rejim: {_text(current.get('regime'))}",
        f"Göreceli güç: {_text(current.get('relative_strength'))}",
        f"Çoklu zaman dilimi: {_text(current.get('multi_timeframe'), 'ek veri yok')}",
        f"Evidence: {_text(current.get('evidence'))}",
    ]
    ax.text(0.068, 0.757, "\n".join(_wrap(line, 105) for line in state_lines), fontsize=10.5, color="#e4ebf5", va="top", linespacing=1.55)

    _box(ax, 0.045, 0.455, 0.44, 0.16, "YAKIN REFERANSLAR")
    location = report.get("location", {}) or {}
    level_lines = [
        _level_line(location.get("nearest_support"), "Alt"),
        _level_line(location.get("nearest_resistance"), "Üst"),
    ]
    ax.text(0.068, 0.566, "\n\n".join(_wrap(line, 48) for line in level_lines), fontsize=10.5, color="#e4ebf5", va="top", linespacing=1.4)

    _box(ax, 0.515, 0.455, 0.44, 0.16, "ELLIOTT HİPOTEZİ")
    wave = (report.get("wave", {}) or {}).get("primary")
    if wave:
        confidence = float(wave.get("confidence") or 0.0) * 100.0
        wave_lines = [
            f"{_text(wave.get('pattern_type'))} · {_text(wave.get('direction'))}",
            f"Durum: {_text(wave.get('active_wave'))}",
            f"Güven: %{confidence:.0f}",
        ]
    else:
        wave_lines = ["Hard-rule geçen hipotez yok."]
    ax.text(0.538, 0.566, "\n".join(_wrap(line, 46) for line in wave_lines), fontsize=10.5, color="#e4ebf5", va="top", linespacing=1.55)

    _box(ax, 0.045, 0.275, 0.44, 0.15, "BEKLEYEN SENARYO")
    ax.text(0.068, 0.377, "\n\n".join(_wrap(line, 48) for line in _scenario_lines(report)), fontsize=10.5, color="#e4ebf5", va="top", linespacing=1.45)

    _box(ax, 0.515, 0.275, 0.44, 0.15, "YAPISAL REFERANSLAR")
    ax.text(0.538, 0.377, "\n".join(_wrap(line, 47) for line in _structural_lines(report)), fontsize=10.5, color="#e4ebf5", va="top", linespacing=1.5)

    _box(ax, 0.045, 0.105, 0.91, 0.14, "ANALİST ÖZETİ")
    summary = _wrap(report.get("summary"), 118)
    location_text = _wrap(location.get("text"), 118)
    ax.text(0.068, 0.198, f"{summary}\n\n{location_text}", fontsize=10.2, color="#dce6f5", va="top", linespacing=1.42)

    ax.text(0.055, 0.055, "V3 preview · Durum raporudur, otomatik AL/SAT sinyali değildir.", fontsize=9.2, color="#71839e", va="bottom")
    ax.text(0.945, 0.055, _text(report.get("timestamp")), fontsize=9.2, color="#71839e", ha="right", va="bottom")

    fig.savefig(output_path, dpi=CARD_DPI, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)
    return output_path
