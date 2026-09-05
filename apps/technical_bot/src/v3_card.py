from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

CARD_WIDTH = 10.8
CARD_HEIGHT = 16.2
CARD_DPI = 100


ROLE_LABELS = {
    "SUPPORT": "Destek",
    "RESISTANCE": "Direnç",
    "FORMER_SUPPORT_RECLAIM": "Eski destek / geri kazanım",
    "RECLAIM_FAILED_SUPPORT": "Geri kazanılamayan eski destek",
    "FORMER_SUPPORT_REJECTION": "Eski destek / reddedilme",
    "RECLAIMED_SUPPORT": "Yeniden kazanılmış destek",
    "FORMER_RESISTANCE_RETEST": "Eski direnç / geri test",
    "BREAKOUT_REJECTED_RESISTANCE": "Reddedilen kırılım direnci",
    "BREAKOUT_RECLAIMED_SUPPORT": "Kırılım sonrası destek",
    "FORMER_RESISTANCE_RETEST_HELD": "Geri testte korunan destek",
    "WAVE_TARGET_ZONE": "Elliott hedef bölgesi",
    "WAVE_INVALIDATION": "Elliott geçersizlik seviyesi",
}

STATE_LABELS = {
    "BELOW_STRUCTURE": "Yapı altı",
    "INSIDE_STRUCTURE": "Yapı içinde",
    "ABOVE_STRUCTURE": "Yapı üstü",
    "UNAVAILABLE": "Belirlenemedi",
    "TRANSITION": "Geçiş",
    "UNDERPERFORMING": "Endeks altı performans",
    "OUTPERFORMING": "Endeks üstü performans",
    "MIXED": "Karışık",
}

SECTION_LABELS = {
    "trend_and_averages": "Trend / Ortalamalar",
    "momentum": "Momentum",
    "participation": "Hacim / Katılım",
    "trend_systems": "Trend Sistemleri",
    "volatility": "Volatilite",
}


def _text(value: Any, fallback: str = "—") -> str:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or fallback


def _human(value: Any) -> str:
    raw = _text(value)
    return STATE_LABELS.get(raw, ROLE_LABELS.get(raw, raw.replace("_", " ").title()))


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
        fontsize=10.5,
        fontweight="bold",
        color="#9fb5d8",
        va="top",
    )


def _level_line(level: dict[str, Any] | None, prefix: str) -> str:
    if not level:
        return f"{prefix}: yakın aktif referans yok"
    return f"{prefix}: {_price(level.get('value'))} · {_human(level.get('role'))}"


def _scenario_lines(report: dict[str, Any]) -> list[str]:
    scenarios = report.get("scenarios", {}) or {}
    result: list[str] = []
    for label, key in (("Yukarı", "up"), ("Aşağı", "down")):
        items = list(scenarios.get(key) or [])
        if items:
            result.append(f"{label}: {_text(items[0].get('confirmation_rule'))}")
    return result or ["Yakın vadede bekleyen senaryo seviyesi yok."]


def _scanner_lines(report: dict[str, Any]) -> list[str]:
    rows = list(report.get("scanner_evidence") or [])
    if not rows:
        return ["Taramabot verisi yok."]
    lines: list[str] = []
    for item in rows[:3]:
        code = _text(item.get("scanner_code"), _text(item.get("scanner_name"), "Tarama"))
        timeframe = _text(item.get("timeframe"))
        side = str(item.get("side") or "NEUTRAL")
        state = str(item.get("state") or "")
        if state == "HISTORICAL":
            direction = "geçmiş AL" if side == "BUY" else "geçmiş SAT" if side == "SELL" else "geçmiş kayıt"
            suffix = " · güncel teyit değil"
        else:
            direction = "AL adayı" if side == "BUY" else "SAT adayı" if side == "SELL" else "nötr"
            suffix = f" · {state.lower()}" if state else ""
        lines.append(f"{timeframe} · {code}: {direction}{suffix}")
    return lines


def _ma_lines(report: dict[str, Any]) -> list[str]:
    rows = list(report.get("ma_support_resistance") or [])
    if not rows:
        return ["MA destek/direnç taraması yok."]
    lines: list[str] = []
    for item in rows[:3]:
        side = "Destek" if item.get("side") == "SUPPORT" else "Direnç" if item.get("side") == "RESISTANCE" else "Seviye"
        low = item.get("zone_low")
        high = item.get("zone_high")
        mid = item.get("zone_mid")
        zone = f"{_price(low)}–{_price(high)}" if low is not None and high is not None else _price(mid)
        ma_names = ", ".join(item.get("ma_list") or [])
        quality = _text(item.get("zone_quality"), "")
        lines.append(f"{_text(item.get('timeframe'))} · {side} {zone} · {quality} · {ma_names}")
    return lines


def _technical_lines(report: dict[str, Any]) -> list[str]:
    sections = report.get("technical_sections") or {}
    lines: list[str] = []
    for key in (
        "trend_and_averages",
        "momentum",
        "participation",
        "trend_systems",
        "volatility",
    ):
        item = sections.get(key) or {}
        interpretation = str(item.get("interpretation") or "").strip()
        if interpretation:
            lines.append(f"{SECTION_LABELS[key]}: {interpretation}")
    return lines or ["Detaylı teknik feature özeti yok."]


def _synthesis_lines(report: dict[str, Any]) -> list[str]:
    synthesis = report.get("technical_synthesis") or {}
    result = [_text(synthesis.get("headline"), _text(report.get("summary")))]
    conflicts = list(synthesis.get("conflicts") or [])
    risks = list(synthesis.get("risks") or [])
    positives = list(synthesis.get("positives") or [])
    if conflicts:
        result.append(f"Çelişki: {conflicts[0]}")
    elif positives:
        result.append(f"Destekleyen: {positives[0]}")
    if risks:
        result.append(f"Risk: {risks[0]}")
    return result


def render_v3_card(report: dict[str, Any], output_path: Path) -> Path:
    """V4 report contract'tan tek sayfalık, business-logic içermeyen kart üretir."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(CARD_WIDTH, CARD_HEIGHT), dpi=CARD_DPI, facecolor="#08111f")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_facecolor("#08111f")

    symbol = _text(report.get("symbol"))
    interval = _text(report.get("interval_label"), _text(report.get("interval")))
    ax.text(0.055, 0.965, f"{symbol} · V4 TEKNİK ANALİZ", fontsize=22, fontweight="bold", color="#f5f8ff", va="top")
    ax.text(0.055, 0.938, f"{interval} · deterministik analiz motoru", fontsize=10.5, color="#8ea1bf", va="top")
    ax.text(0.945, 0.965, _price(report.get("price")), fontsize=24, fontweight="bold", color="#f5f8ff", ha="right", va="top")
    ax.text(0.945, 0.938, _pct(report.get("change_pct")), fontsize=11.5, color="#c1ccdd", ha="right", va="top")

    synthesis = report.get("technical_synthesis") or {}
    headline = _wrap(synthesis.get("headline") or report.get("headline"), 82)
    ax.text(0.055, 0.897, headline, fontsize=13.5, fontweight="bold", color="#d9e5f7", va="top", linespacing=1.30)

    _box(ax, 0.045, 0.748, 0.91, 0.115, "PİYASA YAPISI")
    current = report.get("current_state", {}) or {}
    market_lines = [
        f"Yapı: {_text(current.get('structure'))}",
        f"Fiyat konumu: {_human(current.get('structure_price_position'))}",
        f"Rejim: {_human(current.get('regime'))} · Göreceli güç: {_human(current.get('relative_strength'))}",
    ]
    ax.text(0.068, 0.819, "\n".join(_wrap(line, 105) for line in market_lines), fontsize=10.2, color="#e4ebf5", va="top", linespacing=1.45)

    _box(ax, 0.045, 0.545, 0.91, 0.18, "TEKNİK BÖLÜM YORUMLARI")
    technical_text = "\n".join(_wrap(line, 108) for line in _technical_lines(report)[:5])
    ax.text(0.068, 0.681, technical_text, fontsize=9.25, color="#e4ebf5", va="top", linespacing=1.35)

    _box(ax, 0.045, 0.405, 0.44, 0.115, "TARAMABOT")
    scanner_text = "\n".join(_wrap(line, 47) for line in _scanner_lines(report))
    ax.text(0.068, 0.477, scanner_text, fontsize=8.8, color="#e4ebf5", va="top", linespacing=1.4)

    _box(ax, 0.515, 0.405, 0.44, 0.115, "DİNAMİK MA DESTEK / DİRENÇ")
    ma_text = "\n".join(_wrap(line, 47) for line in _ma_lines(report))
    ax.text(0.538, 0.477, ma_text, fontsize=8.6, color="#e4ebf5", va="top", linespacing=1.38)

    _box(ax, 0.045, 0.275, 0.44, 0.105, "BİRLEŞİK YAKIN SEVİYELER")
    location = report.get("location", {}) or {}
    level_lines = [
        _level_line(location.get("nearest_support"), "Alt"),
        _level_line(location.get("nearest_resistance"), "Üst"),
    ]
    ax.text(0.068, 0.340, "\n\n".join(_wrap(line, 47) for line in level_lines), fontsize=9.5, color="#e4ebf5", va="top", linespacing=1.35)

    _box(ax, 0.515, 0.275, 0.44, 0.105, "SENARYO / ELLIOTT BAĞLAMI")
    scenario_lines = _scenario_lines(report)
    wave = (report.get("wave", {}) or {}).get("primary")
    if wave:
        scenario_lines.append(
            f"Elliott: {_human(wave.get('pattern_type'))} · {_human(wave.get('active_wave'))} · güven %{float(wave.get('confidence') or 0) * 100:.0f}"
        )
    ax.text(0.538, 0.340, "\n".join(_wrap(line, 47) for line in scenario_lines[:3]), fontsize=9.2, color="#e4ebf5", va="top", linespacing=1.38)

    _box(ax, 0.045, 0.105, 0.91, 0.145, "TEKNİK SENTEZ")
    synth_text = "\n\n".join(_wrap(line, 110) for line in _synthesis_lines(report))
    ax.text(0.068, 0.207, synth_text, fontsize=9.7, color="#dce6f5", va="top", linespacing=1.38)

    ax.text(0.055, 0.055, "V4 preview · Durum analizi; otomatik AL/SAT emri değildir.", fontsize=9.0, color="#71839e", va="bottom")
    ax.text(0.945, 0.055, _text(report.get("timestamp")), fontsize=9.0, color="#71839e", ha="right", va="bottom")

    fig.savefig(output_path, dpi=CARD_DPI, facecolor=fig.get_facecolor(), bbox_inches=None)
    plt.close(fig)
    return output_path
