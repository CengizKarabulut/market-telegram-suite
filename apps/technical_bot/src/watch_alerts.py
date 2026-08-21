"""Takip listesi ve seviye uyarıları.

Kullanıcı bir sembolü takibe aldığında, o anki kurulumun çözülme eşikleri
kaydedilir. Bot seans içinde bu sembolleri periyodik kontrol eder ve fiyat
eşiklerden birini kapanışla aştığında haber verir.

Uyarı, eşiğin aşıldığını bildirir; ne yapılması gerektiğini söylemez.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

WATCH_PATH = Path("reports/watchlist.json")
MAX_WATCHED = 20


@dataclass
class Watch:
    ticker: str
    interval: str
    upper: float
    lower: float
    setup: str
    added_at: str
    triggered: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_watches(path: Path = WATCH_PATH) -> dict[str, Watch]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    watches: dict[str, Watch] = {}
    for ticker, item in payload.items():
        try:
            watches[str(ticker)] = Watch(
                ticker=str(item["ticker"]),
                interval=str(item.get("interval", "1d")),
                upper=float(item["upper"]),
                lower=float(item["lower"]),
                setup=str(item.get("setup", "")),
                added_at=str(item.get("added_at", "")),
                triggered=str(item.get("triggered", "")),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return watches


def save_watches(watches: dict[str, Watch], path: Path = WATCH_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({ticker: watch.as_dict() for ticker, watch in watches.items()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def add_watch(watches: dict[str, Watch], watch: Watch) -> tuple[dict[str, Watch] | None, str]:
    if watch.ticker in watches:
        updated = dict(watches)
        updated[watch.ticker] = watch
        return updated, f"{watch.ticker} takip seviyeleri güncellendi: {watch.lower:,.2f} – {watch.upper:,.2f}"
    if len(watches) >= MAX_WATCHED:
        return None, f"Takip listesi dolu (en fazla {MAX_WATCHED}). Önce /takip sil SEMBOL ile yer açın."
    updated = dict(watches)
    updated[watch.ticker] = watch
    return updated, f"{watch.ticker} takibe alındı. Uyarı eşikleri: {watch.lower:,.2f} altı / {watch.upper:,.2f} üstü kapanış."


def remove_watch(watches: dict[str, Watch], ticker: str) -> tuple[dict[str, Watch] | None, str]:
    symbol = ticker.strip().upper()
    if symbol not in watches:
        return None, f"{symbol} takip listesinde yok."
    updated = dict(watches)
    updated.pop(symbol)
    return updated, f"{symbol} takipten çıkarıldı."


def describe(watches: dict[str, Watch]) -> str:
    if not watches:
        return "Takip listesi boş. Eklemek için: /takip THYAO"
    lines = [f"Takip listesi ({len(watches)}/{MAX_WATCHED}):"]
    for watch in watches.values():
        state = " — uyarı verildi" if watch.triggered else ""
        lines.append(f"{watch.ticker} ({watch.interval}): {watch.lower:,.2f} – {watch.upper:,.2f}{state}")
    lines.append("")
    lines.append("Çıkarmak için: /takip sil THYAO")
    return "\n".join(lines)


def check_break(watch: Watch, close: float) -> str:
    """Kapanış eşiği aştı mı? Aştıysa uyarı metnini döndürür."""
    if not math.isfinite(close) or watch.triggered:
        return ""
    if close > watch.upper:
        return (
            f"🔔 {watch.ticker} — yukarı eşik aşıldı\n"
            f"Kapanış {close:,.2f}, izlenen üst seviye {watch.upper:,.2f}.\n"
            f"Takibe alındığındaki kurulum: {watch.setup or '—'}.\n"
            "Bu bir alım/satım önerisi değildir; yalnızca izlenen seviyenin aşıldığını bildirir."
        )
    if close < watch.lower:
        return (
            f"🔔 {watch.ticker} — aşağı eşik aşıldı\n"
            f"Kapanış {close:,.2f}, izlenen alt seviye {watch.lower:,.2f}.\n"
            f"Takibe alındığındaki kurulum: {watch.setup or '—'}.\n"
            "Bu bir alım/satım önerisi değildir; yalnızca izlenen seviyenin aşıldığını bildirir."
        )
    return ""
