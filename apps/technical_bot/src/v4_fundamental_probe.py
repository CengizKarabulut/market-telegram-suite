from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import borsapy as bp
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_core.fundamental_sources import parse_kap_financial_report_html  # noqa: E402


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _disclosure_id(url: str) -> int | None:
    match = re.search(r"/Bildirim/(\d+)", str(url or ""), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _save_frame(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, encoding="utf-8-sig")
    return {
        "path": str(path),
        "shape": list(frame.shape),
        "columns": [str(item) for item in frame.columns],
        "rows": [str(item) for item in frame.index],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 gerçek finansal veri kaynak probu")
    parser.add_argument("symbol")
    parser.add_argument("--last-n", type=int, default=8)
    parser.add_argument("--output", default="reports/v4_fundamental_probe")
    parser.add_argument("--financial-group", default="XI_29")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper().removesuffix(".IS").removesuffix(".E")
    target = Path(args.output) / symbol
    target.mkdir(parents=True, exist_ok=True)
    ticker = bp.Ticker(symbol)

    tables: dict[str, dict[str, Any]] = {}
    balance = ticker.get_balance_sheet(
        quarterly=True,
        last_n=args.last_n,
        financial_group=args.financial_group,
    )
    income = ticker.get_income_stmt(
        quarterly=True,
        last_n=args.last_n,
        financial_group=args.financial_group,
    )
    cashflow = ticker.get_cashflow(
        quarterly=True,
        last_n=args.last_n,
        financial_group=args.financial_group,
    )
    annual_balance = ticker.get_balance_sheet(
        quarterly=False,
        last_n=4,
        financial_group=args.financial_group,
    )
    annual_income = ticker.get_income_stmt(
        quarterly=False,
        last_n=4,
        financial_group=args.financial_group,
    )
    annual_cashflow = ticker.get_cashflow(
        quarterly=False,
        last_n=4,
        financial_group=args.financial_group,
    )

    for name, frame in (
        ("balance_quarterly", balance),
        ("income_quarterly", income),
        ("cashflow_quarterly", cashflow),
        ("balance_annual", annual_balance),
        ("income_annual", annual_income),
        ("cashflow_annual", annual_cashflow),
    ):
        tables[name] = _save_frame(frame, target / f"{name}.csv")

    news = ticker.news
    _save_frame(news, target / "kap_news.csv")
    financial_filings: list[dict[str, Any]] = []
    if not news.empty:
        for _, row in news.iterrows():
            title = str(row.get("Title") or "")
            if "finansal rapor" not in title.casefold():
                continue
            url = str(row.get("URL") or "")
            disclosure_id = _disclosure_id(url)
            raw_html = ticker.get_news_content(disclosure_id) if disclosure_id is not None else None
            parsed = parse_kap_financial_report_html(
                raw_html or "",
                disclosure_id=disclosure_id,
                title=title,
                url=url or None,
            )
            item = asdict(parsed)
            item["news_date"] = str(row.get("Date") or "")
            financial_filings.append(item)

    payload = {
        "symbol": symbol,
        "financial_group": args.financial_group,
        "source_contract": {
            "financial_values": "borsapy/IsYatirim",
            "publication_metadata": "borsapy/KAP",
            "borsapy_ttm_used": False,
            "point_in_time_note": (
                "Provider TTM/availability is not accepted as canonical; exact KAP published_at "
                "must be paired with explicit-period statement values before TTM assembly."
            ),
        },
        "tables": tables,
        "financial_filings": financial_filings,
    }
    output = target / "probe.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    print(f"V4 fundamental probe: {symbol}")
    for name, meta in tables.items():
        print(f"{name}: {meta['shape']} · columns={meta['columns']}")
    print(f"KAP finansal rapor kaydı: {len(financial_filings)}")
    for item in financial_filings:
        print(
            "KAP FR: "
            f"id={item.get('disclosure_id')} "
            f"published_at={item.get('published_at')} "
            f"period={item.get('period_label')} "
            f"period_end={item.get('period_end')}"
        )
    print(f"Probe: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
