"""Tarayıcı komut satırı arayüzü.

Sembolleri parti parti indirir, iki aşamalı taramayı çalıştırır ve sonucu her
durumda raporlar. Eşleşme çıkmasa veya semboller hata verse bile özet gönderilir;
sessiz başarısızlık, taramanın hiç çalışmadığını fark etmemeye yol açar.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.analyst_card import render_analyst_cards, standardize_pages
from src.intervals import resolve
from src.scan_card import render_scan_cards
from src.scan_state import (
    MARKET_TIMEZONE,
    load_state,
    mark_reported,
    save_state,
    select_new,
)
from src.screener import (
    SCREENS,
    chunked,
    default_options,
    merge_interval_results,
    run_screen,
)
from src.stock_dashboard import (
    ScanConfig,
    build_status,
    calculate_indicators,
    render_report_pages,
)
from src.telegram_client import send_analyst_cards
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


def _result_line(item: dict[str, Any], labels: dict[str, str]) -> list[str]:
    """Bir eşleşmenin iki satırlık gösterimi; kurulum adı etiketle tekrarlanmaz."""
    setup = str(item.get("setup", ""))
    tags = [labels.get(name, name) for name in item["screens"]]
    # "Trend devamı | Trend devamı" gibi tekrarları önle.
    tags = [tag for tag in tags if tag.casefold() != setup.casefold()]
    excess = item.get("excess_return_20")
    rs = ""
    if isinstance(excess, (int, float)) and math.isfinite(float(excess)):
        rs = f" | XU100 {excess:+.1f} puan"
    head = f"• {item['ticker']} {item['close']:.2f} | RVOL {item['rvol']:.2f}x | BB %{item['bb_width_percentile']:.0f}{rs}"
    detail = setup or ""
    if tags:
        detail = f"{detail} — {', '.join(tags)}" if detail else ", ".join(tags)
    lines = [head, f"   {detail}"]
    for note in item.get("notes", [])[:1]:
        lines.append(f"   ⚠ {note}")
    return lines


def _error_lines(payload: dict[str, Any]) -> list[str]:
    """Veri yetersizliğini gerçek arızadan ayırır."""
    kinds = payload.get("error_kinds", {})
    if not kinds:
        return []
    lines = [""]
    short = kinds.get("kisa_gecmis", [])
    missing = kinds.get("veri_yok", [])
    broken = kinds.get("ariza", [])
    if short or missing:
        lines.append(f"ℹ Taranamayan {len(short) + len(missing)} sembol: yetersiz geçmiş veya veri yok (yeni halka arz, fon, varant).")
    if broken:
        sample = ", ".join(broken[:6])
        lines.append(f"⚠ Gerçek hata veren {len(broken)} sembol: {sample}")
        if len(broken) > 6:
            lines.append("   (tam liste JSON çıktısında)")
    return lines


def build_symbol_report(
    ticker: str,
    prices: pd.DataFrame,
    directory: Path,
    interval: str,
    detail: str = "kompakt",
) -> list[Path]:
    """Eşleşen sembol için tek hisse raporunun aynısını üretir."""
    data = calculate_indicators(prices, interval)
    config = ScanConfig(ticker=ticker, market="BIST", interval=interval, report_detail=detail)
    status = build_status(data, config, ticker)
    target = directory / ticker
    pages = render_report_pages(data, status, target, f"{ticker}_rapor")
    cards = render_analyst_cards(status, target, f"{ticker}_kart")
    standardize_pages(pages + cards)
    return pages + cards


def fetch_benchmark(symbol: str, period: str, interval: str) -> pd.Series | None:
    """Göreceli güç için endeksi bir kez indirir; hata taramayı durdurmaz."""
    if not symbol:
        return None
    try:
        import borsapy as bp

        frame = bp.Index(symbol.removesuffix(".IS")).history(period=period, interval=interval)
        clean = _normalize(frame)
        return clean["Close"] if not clean.empty else None
    except Exception:  # noqa: BLE001 -- benchmark yoksa tarama yine de çalışmalı
        return None


def summary_text(payload: dict[str, Any], universe_source: str, elapsed: float) -> str:
    """Eşleşme olsun olmasın gönderilen özet."""
    results = payload["results"][:MAX_TELEGRAM_ROWS]
    broken = len(payload.get("error_kinds", {}).get("ariza", []))
    lines = [
        "🔎 BIST Teknik Tarama",
        f"Evren: {payload['requested']} sembol ({universe_source})",
        f"İşlenen: {payload['processed']} | Eşleşen: {payload['matched']} | Likidite elemesi: {payload['filtered_out']} | Arıza: {broken}",
        f"Süre: {elapsed / 60:.1f} dk",
        "",
    ]
    if results:
        labels = {name: SCREENS[name]["label"] for name in SCREENS}
        for item in results:
            lines.extend(_result_line(item, labels))
        if payload["matched"] > len(results):
            lines.append(f"… ve {payload['matched'] - len(results)} sembol daha (tam liste JSON çıktısında).")
    else:
        lines.append("Bu taramada koşulları karşılayan sembol bulunamadı.")
    lines.extend(_error_lines(payload))
    lines.extend(["", "Durum taramasıdır; AL/SAT sinyali veya yatırım tavsiyesi değildir."])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BIST geneli teknik durum taraması yapar.")
    parser.add_argument("--universe", default="auto", choices=["auto", "provider", "file"], help="Sembol kaynağı")
    parser.add_argument("--watchlist", default="watchlist.txt", help="Yerel sembol listesi (yedek kaynak)")
    parser.add_argument("--limit", type=int, default=0, help="En fazla kaç sembol taransın (0 = sınırsız)")
    parser.add_argument("--period", default="", help="Boşsa mum aralığının varsayılan dönemi kullanılır")
    parser.add_argument("--interval", default="1d", help="Tek aralık veya virgülle birden fazla (ör. 1h,1d)")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--screens", default="", help="Virgülle ayrılmış tarama adları; boşsa hepsi")
    parser.add_argument("--bb-rank-max", type=float, default=default_options()["bb_rank_max"])
    parser.add_argument("--rvol-min", type=float, default=default_options()["rvol_min"])
    parser.add_argument("--rvol-spike", type=float, default=default_options()["rvol_spike"])
    parser.add_argument("--min-turnover", type=float, default=default_options()["min_turnover"])
    parser.add_argument("--benchmark", default="XU100", help="Göreceli güç endeksi (boş = kapalı)")
    parser.add_argument("--output", default="reports/screener.json")
    parser.add_argument("--report-top", type=int, default=3, help="Kaç yeni eşleşme için tam rapor üretilsin (0 = kapalı)")
    parser.add_argument("--report-detail", default="kompakt", choices=["kompakt", "dengeli", "tam"])
    parser.add_argument("--state", default="reports/scan_state.json", help="Gün içi tekrar önleme durumu")
    parser.add_argument("--title", default="BIST Teknik Tarama")
    parser.add_argument("--send-telegram", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # 1 saatlik veride 2 yıllık dönem gereksiz ağırdır; aralığın kendi varsayılanı kullanılır.
    universe = load_universe(args.universe, Path(args.watchlist))
    symbols = universe.symbols[: args.limit] if args.limit > 0 else universe.symbols
    print(f"Evren: {len(symbols)} sembol ({universe.source}) | aralık(lar): {args.interval}")

    enabled = [name.strip() for name in args.screens.split(",") if name.strip()] or list(SCREENS)
    options = {
        "bb_rank_max": args.bb_rank_max,
        "rvol_min": args.rvol_min,
        "rvol_spike": args.rvol_spike,
        "min_turnover": args.min_turnover,
    }
    intervals = [item.strip() for item in args.interval.split(",") if item.strip()] or ["1d"]
    started = time.perf_counter()
    payloads: dict[str, dict[str, Any]] = {}
    scan_frames: dict[str, Any] = {}
    for interval in intervals:
        interval_period = args.period or resolve(interval).default_period
        benchmark = fetch_benchmark(args.benchmark, interval_period, interval)
        if benchmark is None:
            print(f"Uyarı: {args.benchmark} verisi alınamadı ({interval}); göreceli güç hesaplanmayacak.")
        print(f"  {interval} taraması başlıyor (dönem {interval_period})…")
        result = run_screen(
            symbols,
            build_fetcher(interval_period, interval),
            options=options,
            enabled=enabled,
            interval=interval,
            batch_size=args.batch_size,
            benchmark=benchmark,
            keep_frames=args.report_top > 0,
        )
        # Rapor üretimi en kısa zaman diliminin verisiyle yapılır.
        for ticker, frame in result.pop("frames", {}).items():
            scan_frames.setdefault(ticker, (interval, frame))
        payloads[interval] = result
        print(f"  {interval}: {result['matched']} eşleşme, {result['processed']} işlendi.")
    payload = merge_interval_results(payloads) if len(payloads) > 1 else payloads[intervals[0]]
    payload.pop("frames", None)
    elapsed = time.perf_counter() - started
    payload["universe_source"] = universe.source
    payload["elapsed_seconds"] = round(elapsed, 1)
    payload["batches"] = len(chunked(symbols, args.batch_size))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"Tarama bitti: {payload['processed']} işlendi, {payload['matched']} eşleşme, {len(payload['errors'])} hata, {elapsed / 60:.1f} dk.")
    print(f"JSON: {output}")

    stamp = datetime.now(MARKET_TIMEZONE).strftime("%d.%m.%Y %H:%M")
    payload["timestamp"] = stamp
    payload["interval"] = intervals[0]
    label = " + ".join(intervals)
    payload["header_line"] = f"{stamp} · {label} tarama"

    reports_dir = output.parent
    scan_cards = render_scan_cards(payload, reports_dir, universe.source, elapsed, title=args.title)
    print(f"{len(scan_cards)} tarama kartı üretildi.")

    # Aynı sembol gün boyu her saat eşleşir; yalnızca yeni veya durumu değişmiş
    # olanlar için tam rapor üretilir, aksi halde kanal tekrarla dolar.
    state_path = Path(args.state)
    reported = load_state(state_path)
    fresh = select_new(payload["results"], reported, args.report_top)
    symbol_images: list[Path] = []
    produced: list[dict[str, Any]] = []
    for item in fresh:
        ticker = item["ticker"]
        try:
            entry = scan_frames.get(ticker)
            if entry is None:
                print(f"  {ticker}: rapor için veri alınamadı, atlanıyor.")
                continue
            report_interval, prices = entry
            images = build_symbol_report(ticker, prices, reports_dir, report_interval, args.report_detail)
            symbol_images.extend(images)
            produced.append(item)
            print(f"  {ticker}: {len(images)} sayfalık rapor üretildi.")
        except Exception as error:  # noqa: BLE001 -- tek sembol raporu taramayı bozmasın
            print(f"  {ticker}: rapor üretilemedi ({type(error).__name__}: {error}).")
    if produced:
        save_state(mark_reported(produced, reported), state_path)

    if args.send_telegram:
        send_analyst_cards(scan_cards, {})
        if symbol_images:
            send_analyst_cards(symbol_images, {})
        print(f"Telegram'a {len(scan_cards) + len(symbol_images)} görsel gönderildi.")
    else:
        print(f"Üretilen görsel: {len(scan_cards) + len(symbol_images)} (gönderim kapalı).")


if __name__ == "__main__":
    main()
