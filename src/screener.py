"""BIST geneli teknik tarayıcı.

600+ sembol için iki aşamalı çalışır:

1. Ucuz aşama: yalnızca gösterge hesabı (~135 ms/sembol). Likidite ve temel
   filtreler burada uygulanır.
2. Pahalı aşama: yalnızca ilk aşamayı geçen sembollerde yapı, hacim profili,
   uyumsuzluk ve kurulum tanıma çalıştırılır (~850 ms/sembol).

Bu ayrım olmadan 600 sembol tek başına 8+ dakika CPU harcar. Tarama sonucu her
durumda raporlanır; eşleşme çıkmasa veya semboller hata verse bile özet
gönderilir, böylece sessiz başarısızlık oluşmaz.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.divergence import detect_divergences
from src.market_context import market_structure, profile_context
from src.semantic_features import build_semantic_features
from src.setup_recognition import build_setup_context
from src.stock_dashboard import MA_PERIODS, calculate_indicators

BATCH_SIZE = 40


def _number(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


@dataclass
class ScreenResult:
    ticker: str
    close: float
    turnover: float
    bb_rank: float
    rvol: float
    atr_pct: float
    rsi: float
    screens: list[str] = field(default_factory=list)
    setup: str = ""
    setup_bias: str = ""
    relative_strength: str = ""
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "close": self.close,
            "turnover": self.turnover,
            "bb_width_percentile": self.bb_rank,
            "rvol": self.rvol,
            "atr_pct": self.atr_pct,
            "rsi": self.rsi,
            "screens": self.screens,
            "setup": self.setup,
            "setup_bias": self.setup_bias,
            "relative_strength": self.relative_strength,
            **self.detail,
        }


def basic_metrics(data: pd.DataFrame) -> dict[str, float]:
    """İlk aşama için gereken ucuz ölçütler."""
    row = data.iloc[-1]
    close = _number(row["Close"])
    volume = _number(row["Volume"])
    baseline = data["Volume"].shift(1).rolling(20, min_periods=5).mean().iloc[-1]
    turnover = _number((data["Close"] * data["Volume"]).tail(20).mean())
    # Pahalı aşamaya girecek sembolleri daraltmak için ucuz fiyat davranışı
    # göstergeleri. Tam kurulum tanıma yerine yalnızca ön eleme amaçlıdır.
    prior_low = _number(data["Low"].iloc[-21:-1].min())
    prior_high = _number(data["High"].iloc[-21:-1].max())
    pierced_down = _number(data["Low"].iloc[-1]) < prior_low <= close
    pierced_up = _number(data["High"].iloc[-1]) > prior_high >= close
    stack_up = all(close > _number(row.get(f"EMA_{period}", math.nan)) for period in (21, 55) if f"EMA_{period}" in data)
    stack_down = all(close < _number(row.get(f"EMA_{period}", math.nan)) for period in (21, 55) if f"EMA_{period}" in data)
    return {
        "pierced_down": bool(pierced_down),
        "pierced_up": bool(pierced_up),
        "stacked": bool(stack_up or stack_down),
        "close": close,
        "volume": volume,
        "turnover": turnover,
        "rvol": volume / _number(baseline) if _number(baseline) > 0 else math.nan,
        "bb_rank": _number(row.get("BB_WIDTH_RANK")),
        "atr_pct": _number(row.get("ATR_PCT")),
        "rsi": _number(row.get("RSI")),
        "adx": _number(row.get("ADX")),
        "macd_hist": _number(row.get("MACD_HIST")),
    }


# Her tarama: (ad, açıklama, ucuz ön koşul, kurulum sonrası koşul)
SCREENS: dict[str, dict[str, Any]] = {
    "sikisma_hacim": {
        "label": "Sıkışma + hacim",
        "description": "Dar Bollinger bandı üzerine ortalama üstü katılım geldi.",
        "cheap": lambda m, o: m["bb_rank"] <= o["bb_rank_max"] and m["rvol"] >= o["rvol_min"],
        "deep": None,
    },
    "hacim_patlamasi": {
        "label": "Hacim patlaması",
        "description": "Hacim son 20 barın ortalamasının belirgin biçimde üzerinde.",
        "cheap": lambda m, o: m["rvol"] >= o["rvol_spike"],
        "deep": None,
    },
    "asiri_bolge": {
        "label": "Uç RSI bölgesi",
        "description": "RSI uç bölgede; tükenme veya devam ayrımı için izlenmeli.",
        "cheap": lambda m, o: m["rsi"] <= 25 or m["rsi"] >= 75,
        "deep": None,
    },
    "basarisiz_kirilim": {
        "label": "Başarısız kırılım",
        "description": "Seviye aşağı/yukarı denendi ama kapanışla teyit edilmedi.",
        "cheap": lambda m, o: m["pierced_down"] or m["pierced_up"],
        "deep": lambda setup: "reddedilme" in str(setup.get("name", "")).casefold(),
    },
    "karar_bolgesi": {
        "label": "Karar bölgesi",
        "description": "Fiyat daralan aralıkta dengede; kırılım yönü henüz belirsiz.",
        "cheap": lambda m, o: m["bb_rank"] <= o["bb_rank_max"] and m["adx"] < 20,
        "deep": lambda setup: "sıkışma" in str(setup.get("name", "")).casefold(),
    },
    "trend_devami": {
        "label": "Trend devamı",
        "description": "Yapı, dizilim ve yönlülük aynı yönde.",
        "cheap": lambda m, o: m["adx"] >= 22 and m["stacked"],
        "deep": lambda setup: str(setup.get("name", "")) == "Trend devamı",
    },
    "tukenme": {
        "label": "Tükenme denemesi",
        "description": "Uyumsuzluk, teknik yoğunlaşma ve momentum aşırılığı bir arada.",
        "cheap": lambda m, o: (m["rsi"] <= 30 or m["rsi"] >= 70) and (m["pierced_down"] or m["pierced_up"]),
        "deep": lambda setup: str(setup.get("name", "")) == "Tükenme denemesi",
    },
}

DEEP_SCREENS = {name for name, screen in SCREENS.items() if screen["deep"]}


def default_options() -> dict[str, float]:
    return {
        "bb_rank_max": 20.0,
        "rvol_min": 1.5,
        "rvol_spike": 3.0,
        "min_turnover": 20_000_000.0,
        "min_price": 1.0,
    }


def passes_liquidity(metrics: dict[str, float], options: dict[str, float]) -> bool:
    """İşlem görmeyen hisseler taramayı kirletmesin diye likidite eşiği."""
    return (
        math.isfinite(metrics["turnover"])
        and metrics["turnover"] >= options["min_turnover"]
        and _number(metrics["close"]) >= options["min_price"]
    )


def deep_context(data: pd.DataFrame) -> dict[str, Any]:
    """Kurulum tanıma için gereken pahalı bağlamı üretir."""
    structure = market_structure(data)
    profile = profile_context(data)
    divergences = detect_divergences(data)
    semantic = build_semantic_features(data, MA_PERIODS, {}, profile, {}, structure, divergences)
    row = data.iloc[-1]
    regime = "Trend / yönlü piyasa" if _number(row.get("ADX")) >= 25 else "Dengeli / sıkışan piyasa" if _number(row.get("ADX")) < 18 else "Geçiş / karma piyasa"
    context = {"regime": {"state": regime, "adx": _number(row.get("ADX"))}, "structure": structure, "profile": profile}
    return build_setup_context(data, context, semantic)


def screen_symbol(
    ticker: str,
    prices: pd.DataFrame,
    options: dict[str, float],
    enabled: Iterable[str],
    interval: str = "1d",
) -> ScreenResult | None:
    """Tek sembolü tarar; eşleşme yoksa None döner."""
    enabled = list(enabled)
    data = calculate_indicators(prices, interval)
    metrics = basic_metrics(data)
    if not passes_liquidity(metrics, options):
        return None
    candidates = [name for name in enabled if SCREENS[name]["cheap"](metrics, options)]
    if not candidates:
        return None
    result = ScreenResult(
        ticker=ticker,
        close=metrics["close"],
        turnover=metrics["turnover"],
        bb_rank=metrics["bb_rank"],
        rvol=metrics["rvol"],
        atr_pct=metrics["atr_pct"],
        rsi=metrics["rsi"],
    )
    needs_deep = [name for name in candidates if name in DEEP_SCREENS]
    shallow = [name for name in candidates if name not in DEEP_SCREENS]
    matched = list(shallow)
    if needs_deep:
        setup_context = deep_context(data)
        setup = setup_context["setup"]
        result.setup = str(setup.get("name", ""))
        result.setup_bias = str(setup.get("bias", ""))
        result.detail["duration"] = setup_context["duration"]["summary"]
        matched.extend(name for name in needs_deep if SCREENS[name]["deep"](setup))
    if not matched:
        return None
    result.screens = matched
    return result


def rank_key(result: ScreenResult) -> tuple:
    """Eşleşmeleri önem sırasına koyar: çok koşul, yüksek katılım, yüksek likidite."""
    return (-len(result.screens), -_number(result.rvol, 0.0), -_number(result.turnover, 0.0))


def chunked(items: list[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def run_screen(
    symbols: list[str],
    fetch: Callable[[list[str]], dict[str, pd.DataFrame]],
    options: dict[str, float] | None = None,
    enabled: Iterable[str] | None = None,
    interval: str = "1d",
    batch_size: int = BATCH_SIZE,
) -> dict[str, Any]:
    """Sembol listesini tarar ve her durumda özet döndürür."""
    options = {**default_options(), **(options or {})}
    enabled = list(enabled or SCREENS.keys())
    unknown = [name for name in enabled if name not in SCREENS]
    if unknown:
        raise ValueError(f"Bilinmeyen tarama: {', '.join(unknown)}")

    matches: list[ScreenResult] = []
    errors: dict[str, str] = {}
    skipped_liquidity = 0
    processed = 0
    for batch in chunked(symbols, batch_size):
        try:
            frames = fetch(batch)
        except Exception as error:  # noqa: BLE001 -- parti hatası taramayı durdurmamalı
            for ticker in batch:
                errors[ticker] = f"parti indirme hatası: {type(error).__name__}"
            continue
        for ticker in batch:
            frame = frames.get(ticker)
            if frame is None or frame.empty:
                errors[ticker] = "veri yok"
                continue
            try:
                processed += 1
                result = screen_symbol(ticker, frame, options, enabled, interval)
                if result is None:
                    skipped_liquidity += 1
                    continue
                matches.append(result)
            except Exception as error:  # noqa: BLE001 -- tek sembol tüm taramayı bozmasın
                errors[ticker] = f"{type(error).__name__}: {error}"[:160]
    matches.sort(key=rank_key)
    return {
        "requested": len(symbols),
        "processed": processed,
        "matched": len(matches),
        "filtered_out": skipped_liquidity,
        "errors": errors,
        "options": options,
        "screens": enabled,
        "results": [item.as_dict() for item in matches],
    }
