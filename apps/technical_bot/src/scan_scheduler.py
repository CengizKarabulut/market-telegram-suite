"""Tarama zamanlayıcısı.

GitHub'ın zamanlanmış koşuları bu depoda güvenilir çalışmadığı için tarama,
sürekli çalışan bot süreci tarafından tetiklenir. Bot Türkiye saatini kontrol
eder; bir slot geçildiyse yalnızca o slota ait çekirdek zaman dilimini başlatır
ve aynı slotu gün içinde ikinci kez tetiklemez.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.intervals import resolve

MARKET_TIMEZONE = ZoneInfo("Europe/Istanbul")
STATE_PATH = Path("reports/scan_schedule.json")
GRACE_MINUTES = 45


@dataclass(frozen=True)
class Slot:
    hour: int
    minute: int
    intervals: str

    @property
    def key(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


# Otomatik BIST tarama takvimi (Europe/Istanbul, hafta ici).
# Her slot yalnızca kendi zaman dilimini çalıştırır.
SLOTS = (
    Slot(10, 20, "1h"),
    Slot(10, 30, "1wk"),
    Slot(10, 45, "1d"),
    Slot(11, 0, "4h"),
    Slot(11, 20, "1h"),
    Slot(12, 20, "1h"),
    Slot(12, 45, "1d"),
    Slot(13, 0, "4h"),
    Slot(13, 20, "1h"),
    Slot(13, 45, "1wk"),
    Slot(14, 20, "1h"),
    Slot(14, 30, "4h"),
    Slot(14, 45, "1d"),
    Slot(15, 20, "1h"),
    Slot(16, 0, "1wk"),
    Slot(16, 20, "1h"),
    Slot(16, 30, "4h"),
    Slot(16, 45, "1d"),
    Slot(17, 20, "1h"),
    Slot(17, 25, "1wk"),
    Slot(17, 30, "4h"),
    Slot(17, 40, "1h"),
    Slot(17, 45, "1d"),
    Slot(18, 20, "1h"),
    Slot(18, 30, "4h"),
    Slot(18, 45, "1d"),
    Slot(19, 0, "1wk"),
)


def now_market() -> datetime:
    return datetime.now(MARKET_TIMEZONE)


def load_state(path: Path = STATE_PATH) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in payload.items()}
    except (OSError, ValueError, AttributeError):
        return {}


def save_state(state: dict[str, str], path: Path = STATE_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def due_slot(current: datetime, state: dict[str, str]) -> Slot | None:
    """Şu an tetiklenmesi gereken en eski çalışmamış slotu döndürür."""
    if current.weekday() >= 5:
        return None
    today = current.date().isoformat()
    for slot in SLOTS:
        if state.get(slot.key) == today:
            continue
        scheduled = current.replace(
            hour=slot.hour,
            minute=slot.minute,
            second=0,
            microsecond=0,
        )
        if current < scheduled:
            continue
        if (current - scheduled).total_seconds() / 60 > GRACE_MINUTES:
            continue
        return slot
    return None


def mark_done(slot: Slot, current: datetime, state: dict[str, str]) -> dict[str, str]:
    updated = dict(state)
    updated[slot.key] = current.date().isoformat()
    return updated


CLOSE_HOUR = 18


def resolve_intervals(value: str | None, current: datetime | None = None) -> str:
    """Aralık girdisini yalnızca 1h/4h/1d/1wk sözleşmesine göre çözer.

    ``auto`` veya boş değer manuel taramada seans saatine göre çekirdek paketi
    seçer. Açık bir değer verilmişse her öğe merkezi interval kayıt defterinden
    geçirilir; emekli edilmiş zaman dilimleri yeniden etkinleştirilemez.
    """
    cleaned = (value or "").strip()
    if cleaned and cleaned.lower() != "auto":
        requested = [item.strip() for item in cleaned.split(",") if item.strip()]
        if not requested:
            raise ValueError("En az bir zaman aralığı gereklidir.")
        canonical = tuple(dict.fromkeys(resolve(item).key for item in requested))
        return ",".join(canonical)
    moment = current or now_market()
    if moment.hour >= CLOSE_HOUR:
        return "1d,1wk"
    return "1h,4h"
