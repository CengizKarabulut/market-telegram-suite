from __future__ import annotations

import math
from typing import Any

from .models import LevelClass, LevelLifecycle, MarketState, TechnicalLevel
from .serialization import ENGINE_VERSION, REPORT_SCHEMA, to_primitive


INTERVAL_LABELS = {
    "5m": "5 dakikalık",
    "15m": "15 dakikalık",
    "30m": "30 dakikalık",
    "45m": "45 dakikalık",
    "1h": "saatlik",
    "2h": "2 saatlik",
    "4h": "4 saatlik",
    "1d": "günlük",
    "1wk": "haftalık",
    "1mo": "aylık",
}


def interval_label(interval: str) -> str:
    return INTERVAL_LABELS.get(str(interval).lower(), str(interval))


def _level_payload(level: TechnicalLevel) -> dict[str, Any]:
    return {
        "value": level.value,
        "zone_low": level.zone_low,
        "zone_high": level.zone_high,
        "source": level.source,
        "role": level.role,
        "lifecycle": level.lifecycle_state.value,
        "class": level.level_class.value,
        "distance_pct": level.distance_pct,
        "distance_atr": level.distance_atr,
        "priority": level.priority,
        "actionability": level.actionability,
        "confidence": level.confidence,
        "age_bars": level.age_bars,
        "tests": level.tests,
        "metadata": level.metadata,
    }


def _nearest(levels: list[TechnicalLevel], price: float, side: str) -> TechnicalLevel | None:
    eligible = [
        level
        for level in levels
        if level.lifecycle_state not in {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}
        and level.level_class != LevelClass.STRUCTURAL
        and ((side == "ABOVE" and level.value > price) or (side == "BELOW" and level.value < price))
    ]
    return min(eligible, key=lambda item: abs(item.value - price), default=None)


def _scenario_payload(state: MarketState, side: str) -> list[dict[str, Any]]:
    return [
        {
            "id": item.get("id"),
            "side": item.get("side"),
            "trigger_type": item.get("trigger_type"),
            "level": item.get("level"),
            "zone": item.get("zone"),
            "state": getattr(item.get("state"), "value", item.get("state")),
            "confirmation_rule": item.get("confirmation_rule"),
            "invalidation_rule": item.get("invalidation_rule"),
            "source": item.get("source"),
            "priority": item.get("priority"),
        }
        for item in state.scenarios
        if str(item.get("side")) == side
    ]


def _wave_payload(state: MarketState) -> dict[str, Any]:
    if not state.wave_hypotheses:
        return {"primary": None, "alternates": []}
    primary = state.wave_hypotheses[0]
    alternates = state.wave_hypotheses[1:3]
    return {
        "primary": to_primitive(primary),
        "alternates": [to_primitive(item) for item in alternates],
    }


def _role_changes(levels: list[TechnicalLevel]) -> list[dict[str, Any]]:
    changed = [
        level
        for level in levels
        if level.lifecycle_state
        in {
            LevelLifecycle.BROKEN_DOWN,
            LevelLifecycle.BROKEN_UP,
            LevelLifecycle.RECLAIMED,
            LevelLifecycle.REJECTED,
        }
    ]
    changed.sort(key=lambda item: (item.age_bars if item.age_bars is not None else 10**9, -item.priority))
    return [_level_payload(level) for level in changed[:6]]


def _summary_text(state: MarketState) -> str:
    interpretation = state.interpretation or {}
    if not interpretation.get("available", True):
        return str(interpretation.get("headline") or "Teknik yorum veri kalitesi nedeniyle kullanılamıyor.")
    pieces = [str(interpretation.get("headline") or "").strip()]
    if interpretation.get("current_state"):
        pieces.append(str(interpretation["current_state"]).strip())
    return " ".join(piece for piece in pieces if piece)


def _scanner_payload(state: MarketState) -> list[dict[str, Any]]:
    rows = list(state.scanner_evidence or [])
    rows.sort(
        key=lambda item: (
            str(item.get("state", "")) not in {"NEW", "ACTIVE", "CONFIRMED"},
            item.get("age_bars") if item.get("age_bars") is not None else 10**9,
            str(item.get("timeframe", "")),
        )
    )
    return rows[:12]


def _ma_level_payload(state: MarketState) -> list[dict[str, Any]]:
    rows = list(state.ma_level_evidence or [])
    rows.sort(
        key=lambda item: (
            abs(float(item.get("distance_atr")))
            if item.get("distance_atr") is not None and math.isfinite(float(item.get("distance_atr")))
            else math.inf,
            -float(item.get("zone_score") or 0.0),
        )
    )
    return rows[:12]


def build_report_contract(state: MarketState) -> dict[str, Any]:
    """Presentation/Telegram/PNG katmanlarının ortak rapor sözleşmesini üretir."""
    label = interval_label(state.interval)
    nearest_below = _nearest(state.levels, state.price, "BELOW")
    nearest_above = _nearest(state.levels, state.price, "ABOVE")
    interpretation = state.interpretation or {}
    quality_blocked = bool(state.confidence.get("critical_data_quality"))

    return to_primitive(
        {
            "schema": REPORT_SCHEMA,
            "engine_version": ENGINE_VERSION,
            "symbol": state.symbol,
            "timestamp": state.timestamp,
            "interval": state.interval,
            "interval_label": label,
            "price": state.price,
            "change_pct": state.change_pct,
            "availability": {
                "analysis": not quality_blocked and bool(interpretation.get("available", True)),
                "wave": bool(state.wave_hypotheses),
                "relative_strength": bool(state.relative_strength.get("available")),
                "multi_timeframe": bool(state.multi_timeframe.get("available")),
                "scanner_evidence": bool(state.scanner_evidence),
                "ma_level_evidence": bool(state.ma_level_evidence),
            },
            "headline": interpretation.get("headline"),
            "summary": _summary_text(state),
            "current_state": {
                "structure": interpretation.get("current_state"),
                "structure_price_position": state.structure.get("price_position"),
                "regime": state.regime.get("state") if state.regime else None,
                "evidence": interpretation.get("evidence"),
                "relative_strength": (
                    f"{state.relative_strength.get('state')} ({state.relative_strength.get('benchmark')})"
                    if state.relative_strength.get("available")
                    else None
                ),
                "multi_timeframe": (
                    state.multi_timeframe.get("state")
                    if state.multi_timeframe.get("available")
                    else None
                ),
            },
            "location": {
                "text": interpretation.get("location"),
                "nearest_support": _level_payload(nearest_below) if nearest_below else None,
                "nearest_resistance": _level_payload(nearest_above) if nearest_above else None,
            },
            "scanner_evidence": _scanner_payload(state),
            "ma_support_resistance": _ma_level_payload(state),
            "wave": _wave_payload(state),
            "scenarios": {
                "up": _scenario_payload(state, "UP"),
                "down": _scenario_payload(state, "DOWN"),
            },
            "role_changes": _role_changes(state.levels),
            "structural_levels": [
                _level_payload(level)
                for level in state.levels
                if level.level_class == LevelClass.STRUCTURAL
            ][:8],
            "evidence_summary": state.evidence_summary,
            "confidence": state.confidence,
            "limitations": state.limitations,
            "language_contract": {
                "close_noun": f"{label} kapanış",
                "bar_noun": f"{label} bar",
                "forbid_generic_daily_wording": state.interval != "1d",
            },
        }
    )


def _fmt_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:.{digits}f}" if math.isfinite(number) else "—"


def _scanner_label(item: dict[str, Any]) -> str:
    state = str(item.get("state") or "").upper()
    side = str(item.get("side", "NEUTRAL"))
    if state == "HISTORICAL":
        side_label = {
            "BUY": "geçmiş AL sinyali",
            "SELL": "geçmiş SAT sinyali",
            "NEUTRAL": "geçmiş nötr kayıt",
        }.get(side, "geçmiş tarama kaydı")
    else:
        side_label = {"BUY": "AL adayı", "SELL": "SAT adayı", "NEUTRAL": "nötr"}.get(side, side)
        if state and state not in {"NEW", "ACTIVE", "CONFIRMED"}:
            side_label = f"{side_label} · {state.lower()}"
    code = item.get("scanner_code") or item.get("scanner_name") or "Tarama"
    timeframe = interval_label(str(item.get("timeframe") or ""))
    age = item.get("age_bars")
    age_text = f" · {age} bar önce" if age is not None else ""
    current_unknown = bool((item.get("data_quality") or {}).get("current_match_unknown"))
    current_text = " · güncel eşleşme ayrıca teyit edilmeli" if current_unknown else ""
    return f"• {timeframe} {code}: {side_label}{age_text}{current_text}"


def _ma_label(item: dict[str, Any]) -> str:
    side = "destek" if item.get("side") == "SUPPORT" else "direnç" if item.get("side") == "RESISTANCE" else "seviye"
    timeframe = interval_label(str(item.get("timeframe") or ""))
    low = item.get("zone_low")
    high = item.get("zone_high")
    mid = item.get("zone_mid")
    if low is not None and high is not None:
        zone = f"{_fmt_number(low)}–{_fmt_number(high)}"
    else:
        zone = _fmt_number(mid)
    quality = item.get("zone_quality") or ""
    ma_list = ", ".join(item.get("ma_list") or [])
    suffix = " · ".join(part for part in (quality, ma_list) if part)
    return f"• {timeframe} {side}: {zone}" + (f" · {suffix}" if suffix else "")


def format_telegram_preview(report: dict[str, Any]) -> str:
    """Yeni presentation sözleşmesinden kompakt, interval-aware Telegram metni."""
    if not report.get("availability", {}).get("analysis", True):
        return (
            f"{report.get('symbol', '—')} · {report.get('interval_label', report.get('interval', ''))}\n"
            f"{report.get('headline') or 'Teknik yorum kullanılamıyor.'}"
        )

    symbol = report.get("symbol", "—")
    label = report.get("interval_label", report.get("interval", ""))
    price = _fmt_number(report.get("price"))
    change_raw = report.get("change_pct")
    try:
        change = float(change_raw)
        change_text = f"%{change:+.2f}" if math.isfinite(change) else "—"
    except (TypeError, ValueError):
        change_text = "—"
    lines = [
        f"{symbol} — V3 Teknik Durum ({label})",
        f"Fiyat: {price} · Değişim: {change_text}",
        "",
        str(report.get("headline") or ""),
    ]
    current = report.get("current_state", {})
    for key, title in (
        ("structure", "Yapı"),
        ("structure_price_position", "Fiyat konumu"),
        ("regime", "Rejim"),
        ("relative_strength", "Göreceli güç"),
        ("multi_timeframe", "Çoklu zaman dilimi"),
    ):
        value = current.get(key)
        if value:
            lines.append(f"{title}: {value}")

    scanner = report.get("scanner_evidence") or []
    if scanner:
        lines.append("")
        lines.append("Taramabot durumu:")
        lines.extend(_scanner_label(item) for item in scanner[:4])

    ma_levels = report.get("ma_support_resistance") or []
    if ma_levels:
        lines.append("")
        lines.append("Dinamik MA destek/direnç taraması:")
        lines.extend(_ma_label(item) for item in ma_levels[:4])

    location = report.get("location", {})
    support = location.get("nearest_support")
    resistance = location.get("nearest_resistance")
    if support or resistance:
        lines.append("")
        lines.append("Birleşik yakın seviyeler:")
        if support:
            lines.append(f"• Alt referans {_fmt_number(support['value'])} — {support['role']}")
        if resistance:
            lines.append(f"• Üst referans {_fmt_number(resistance['value'])} — {resistance['role']}")

    wave = report.get("wave", {}).get("primary")
    if wave:
        lines.append("")
        lines.append(
            f"Elliott bağlamı: {wave.get('pattern_type')} / {wave.get('direction')} · güven %{float(wave.get('confidence') or 0) * 100:.0f}"
        )

    scenarios = report.get("scenarios", {})
    if scenarios.get("up"):
        lines.append("")
        lines.append("Yukarı senaryo:")
        lines.extend(f"• {item['confirmation_rule']}" for item in scenarios["up"][:3])
    if scenarios.get("down"):
        lines.append("")
        lines.append("Aşağı senaryo:")
        lines.extend(f"• {item['confirmation_rule']}" for item in scenarios["down"][:3])

    changes = report.get("role_changes", [])
    if changes:
        lines.append("")
        lines.append("Rol değiştiren seviyeler:")
        lines.extend(
            f"• {_fmt_number(item['value'])} — {item['role']} ({item['lifecycle']})"
            for item in changes[:3]
        )
    return "\n".join(line for line in lines if line is not None).strip()
