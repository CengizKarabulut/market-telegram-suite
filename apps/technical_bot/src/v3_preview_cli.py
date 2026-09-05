from __future__ import annotations

import argparse
from pathlib import Path

from market_core.external_io import (
    load_ma_watchlist_rows,
    load_scanner_snapshot_rows,
    load_taramabot_state_rows,
)
from src.stock_dashboard import (
    ScanConfig,
    calculate_indicators,
    download_benchmark,
    download_prices,
)
from src.v3_card import render_v3_card
from src.v3_preview import build_v3_preview, write_preview_json
from src.v3_telegram import send_v3_preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Market Analysis Engine V3/V4 gerçek veri önizlemesi")
    parser.add_argument("symbol", help="BIST sembolü, ör. ZGYO")
    parser.add_argument("--interval", default="1d", help="5m,15m,30m,1h,2h,4h,1d,1wk,1mo")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--provider", default="AUTO")
    parser.add_argument("--benchmark", default="XU100")
    parser.add_argument("--output", default="reports/v3_preview")
    parser.add_argument(
        "--scanner-state",
        default="",
        help="Taramabot state.json; yalnız geçmişte yayımlanmış sinyalleri HISTORICAL olarak ekler.",
    )
    parser.add_argument(
        "--scanner-snapshot",
        default="",
        help="Versioned/current scanner snapshot JSON; varsa güncel tarama satırlarını ekler.",
    )
    parser.add_argument(
        "--ma-watchlist",
        default="",
        help="ma-reaction-scanner ma_watchlist.csv dosyası.",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="Üretilen V3/V4 metin + kartı teknik Telegram hedefine gönderir.",
    )
    return parser.parse_args()


def _existing(path_value: str) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists():
        print(f"V4 external evidence: dosya bulunamadı, atlandı: {path}")
        return None
    return path


def main() -> int:
    args = parse_args()
    ticker = args.symbol.strip().upper().removesuffix(".IS").removesuffix(".E")
    config = ScanConfig(
        ticker=ticker,
        market="BIST",
        interval=args.interval,
        period=args.period,
        provider=args.provider,
        benchmark=args.benchmark,
    )
    symbol, prices = download_prices(config)
    data = calculate_indicators(prices, args.interval)

    benchmark_data = None
    benchmark_name = args.benchmark
    try:
        benchmark_name, benchmark_data = download_benchmark(config)
    except Exception as exc:  # noqa: BLE001 - preview benchmark optional boundary
        print(f"V3 preview: benchmark alınamadı ({exc}); relative strength unavailable olacak.")

    scanner_rows = []
    scanner_state = _existing(args.scanner_state)
    if scanner_state is not None:
        scanner_rows.extend(load_taramabot_state_rows(scanner_state, symbol=ticker))
        print(f"V4 external evidence: {len(scanner_rows)} taramabot geçmiş sinyali yüklendi.")

    scanner_snapshot = _existing(args.scanner_snapshot)
    if scanner_snapshot is not None:
        current_rows = load_scanner_snapshot_rows(scanner_snapshot, symbol=ticker)
        scanner_rows = current_rows + scanner_rows
        print(f"V4 external evidence: {len(current_rows)} güncel scanner snapshot satırı yüklendi.")

    ma_rows = []
    ma_watchlist = _existing(args.ma_watchlist)
    if ma_watchlist is not None:
        ma_rows = load_ma_watchlist_rows(ma_watchlist, symbol=ticker)
        print(f"V4 external evidence: {len(ma_rows)} MA destek/direnç bölgesi yüklendi.")

    state, report, text = build_v3_preview(
        data,
        symbol=symbol,
        interval=args.interval,
        benchmark_data=benchmark_data,
        benchmark_name=benchmark_name,
        scanner_rows=scanner_rows,
        ma_level_rows=ma_rows,
    )
    target = Path(args.output) / ticker
    state_path, report_path = write_preview_json(state, report, target, ticker)
    text_path = target / f"{ticker}_telegram_v3.txt"
    text_path.write_text(text + "\n", encoding="utf-8")
    card_path = render_v3_card(report, target / f"{ticker}_card_v3.png")

    if args.telegram:
        send_v3_preview(
            text,
            card_path,
            symbol=ticker,
            interval_label=str(report.get("interval_label") or args.interval),
        )
        print("Telegram: V3/V4 preview metni ve kartı gönderildi.")

    print(text)
    print(f"\nMarketState: {state_path}")
    print(f"Report: {report_path}")
    print(f"Telegram preview: {text_path}")
    print(f"V3/V4 card: {card_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
