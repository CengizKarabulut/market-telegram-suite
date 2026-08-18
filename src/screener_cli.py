"""Tarayıcı komut satırı arayüzü.

Sembolleri parti parti indirir, iki aşamalı taramayı çalıştırır ve sonucu her
durumda raporlar. Eşleşme çıkmasa veya semboller hata verse bile özet gönderilir;
sessiz başarısızlık, taramanın hiç çalışmadığını fark etmemeye yol açar.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from src.screener import SCREENS, chunked, default_options, run_screen
from src.telegram_client import send_text
from src.universe import load_universe

MAX_RETRIES = 3
BACKOFF_SECONDS = 5.0
MAX_TELEGRAM_ROWS = 25


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(column in frame.columns for column in required):
        return pd.DataFrame()
    clean = frame[required].dropna(subset=["Open", "High", "Low", "Close"]).copy()
    clean["Volume"] = clean["Volume"].fillna(0.0)
    return clean


def build_fetcher(period: str, interval: str, sleep: float = BACKOFF_SECONDS):
    """borsapy toplu indirme; hız sınırında artan bekleme ile yeniden dener."""
    import borsapy as bp

    def fetch(batch: list[str]) -> dict[str, pd.DataFrame]:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                raw = bp.download(batch, period=period, interval=interval, group_by="ticker", progress=False)
                break
            except Exception as error:
                last_error = error
                if attempt == MAX_RETRIES - 1:
                    raise
                time.sleep(sleep * (attempt + 1))
        else:  # pragma: no cover - döngü ya break ya raise ile biter
            raise last_error or RuntimeError("indirme başarısız")
        frames: dict[str, pd.DataFrame] = {}
        for ticker in batch:
            try:
                frame = raw[ticker] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                continue
            normalized = _normalize(frame)
            if not normalized.empty:
                frames[ticker] = normalized
        return frames

    return fetch


def summary_text(payload: dict[str, Any], universe_source: str, elapsed: float) -> str:
    """Eşleşme olsun olmasın gönderilen özet."""
    results = payload["results"][:MAX_TELEGRAM_ROWS]
    lines = [
        "🔎 BIST Teknik Tarama",
        f"Evren: {payload['requested']} sembol ({universe_source})",
        f"İşlenen: {payload['processed']} | Eşleşen: {payload['matched']} | Likidite elemesi: {payload['filtered_out']} | Hata: {len(payload['errors'])}",
        f"Süre: {elapsed / 60:.1f} dk",
        "",
    ]
    if results:
        labels = {name: SCREENS[name]["label"] for name in SCREENS}
        for item in results:
            tags = ", ".join(labels.get(name, name) for name in item["screens"])
            setup = f" | {item['setup']}" if item.get("setup") else ""
            lines.append(f"• {item['ticker']} {item['close']:.2f} | RVOL {item['rvol']:.2f}x | BB %{item['bb_width_percentile']:.0f}{setup}")
            lines.append(f"   {tags}")
        if payload["matched"] > len(results):
            lines.append(f"… ve {payload['matched'] - len(results)} sembol daha (tam liste JSON çıktısında).")
    else:
        lines.append("Bu taramada koşulları karşılayan sembol bulunamadı.")
    if payload["errors"]:
        sample = list(payload["errors"].items())[:5]
        lines.extend(["", "⚠ Hata veren semboller: " + ", ".join(ticker for ticker, _ in sample)])
        if len(payload["errors"]) > len(sample):
            lines.append(f"   (toplam {len(payload['errors'])} sembol; ayrıntı JSON çıktısında)")
    lines.extend(["", "Durum taramasıdır; AL/SAT sinyali veya yatırım tavsiyesi değildir."])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BIST geneli teknik durum taraması yapar.")
    parser.add_argument("--universe", default="auto", choices=["auto", "provider", "file"], help="Sembol kaynağı")
    parser.add_argument("--watchlist", default="watchlist.txt", help="Yerel sembol listesi (yedek kaynak)")
    parser.add_argument("--limit", type=int, default=0, help="En fazla kaç sembol taransın (0 = sınırsız)")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--screens", default="", help="Virgülle ayrılmış tarama adları; boşsa hepsi")
    parser.add_argument("--bb-rank-max", type=float, default=default_options()["bb_rank_max"])
    parser.add_argument("--rvol-min", type=float, default=default_options()["rvol_min"])
    parser.add_argument("--rvol-spike", type=float, default=default_options()["rvol_spike"])
    parser.add_argument("--min-turnover", type=float, default=default_options()["min_turnover"])
    parser.add_argument("--output", default="reports/screener.json")
    parser.add_argument("--send-telegram", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = load_universe(args.universe, Path(args.watchlist))
    symbols = universe.symbols[: args.limit] if args.limit > 0 else universe.symbols
    print(f"Evren: {len(symbols)} sembol ({universe.source})")

    enabled = [name.strip() for name in args.screens.split(",") if name.strip()] or list(SCREENS)
    options = {
        "bb_rank_max": args.bb_rank_max,
        "rvol_min": args.rvol_min,
        "rvol_spike": args.rvol_spike,
        "min_turnover": args.min_turnover,
    }
    started = time.perf_counter()
    payload = run_screen(
        symbols,
        build_fetcher(args.period, args.interval),
        options=options,
        enabled=enabled,
        interval=args.interval,
        batch_size=args.batch_size,
    )
    elapsed = time.perf_counter() - started
    payload["universe_source"] = universe.source
    payload["elapsed_seconds"] = round(elapsed, 1)
    payload["batches"] = len(chunked(symbols, args.batch_size))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Tarama bitti: {payload['processed']} işlendi, {payload['matched']} eşleşme, {len(payload['errors'])} hata, {elapsed / 60:.1f} dk.")
    print(f"JSON: {output}")
    if args.send_telegram:
        send_text(summary_text(payload, universe.source, elapsed))
        print("Özet Telegram'a gönderildi.")


if __name__ == "__main__":
    main()
