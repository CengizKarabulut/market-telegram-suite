from __future__ import annotations

import argparse
from pathlib import Path

from src.stock_dashboard import ScanConfig, calculate_indicators, download_benchmark, download_prices
from src.v3_preview import build_v3_preview, write_preview_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Market Analysis Engine V3 gerçek veri önizlemesi")
    parser.add_argument("symbol", help="BIST sembolü, ör. ZGYO")
    parser.add_argument("--interval", default="1d", help="5m,15m,30m,1h,2h,4h,1d,1wk,1mo")
    parser.add_argument("--period", default="2y")
    parser.add_argument("--provider", default="AUTO")
    parser.add_argument("--benchmark", default="XU100")
    parser.add_argument("--output", default="reports/v3_preview")
    return parser.parse_args()


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

    state, report, text = build_v3_preview(
        data,
        symbol=symbol,
        interval=args.interval,
        benchmark_data=benchmark_data,
        benchmark_name=benchmark_name,
    )
    target = Path(args.output) / ticker
    state_path, report_path = write_preview_json(state, report, target, ticker)
    text_path = target / f"{ticker}_telegram_v3.txt"
    text_path.write_text(text + "\n", encoding="utf-8")

    print(text)
    print(f"\nMarketState: {state_path}")
    print(f"Report: {report_path}")
    print(f"Telegram preview: {text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
