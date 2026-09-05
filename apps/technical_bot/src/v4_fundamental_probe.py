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

from market_core.fundamental_sources import (
    parse_kap_financial_report_html,
)


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


def _fetch_kap_news(ticker: Any, symbol: str, limit: int) -> tuple[pd.DataFrame, str]:
    """Fetch deeper KAP history while keeping a public-property fallback.

    ``Ticker.news`` intentionally returns only the provider default window. The
    fundamental probe needs several prior financial-report publication times for
    point-in-time TTM, so it asks the already-instantiated KAP provider for a
    larger disclosure window. If the provider internals change, the probe fails
    soft to ``ticker.news`` rather than pretending older filing metadata exists.
    """
    try:
        provider_getter = getattr(ticker, "_get_kap", None)
        if callable(provider_getter):
            provider = provider_getter()
            get_disclosures = getattr(provider, "get_disclosures", None)
            if callable(get_disclosures):
                frame = get_disclosures(symbol, limit=limit)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame, "borsapy/KAP.get_disclosures"
    except Exception:
        pass
    return ticker.news, "borsapy/Ticker.news_fallback"


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 gerçek finansal veri kaynak probu")
    parser.add_argument("symbol")
    parser.add_argument("--last-n", type=int, default=8)
    parser.add_argument("--output", default="reports/v4_fundamental_probe")
    parser.add_argument("--financial-group", default="XI_29")
    parser.add_argument("--kap-limit", type=int, default=120)
    parser.add_argument("--financial-filing-limit", type=int, default=16)
    args = parser.parse_args()

    if args.kap_limit < 20:
        parser.error("--kap-limit en az 20 olmalıdır")
    if args.financial_filing_limit < 1:
        parser.error("--financial-filing-limit en az 1 olmalıdır")

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

    news, kap_history_source = _fetch_kap_news(ticker, symbol, args.kap_limit)
    _save_frame(news, target / "kap_news.csv")
    financial_filings: list[dict[str, Any]] = []
    if not news.empty:
        financial_rows = [
            row
            for _, row in news.iterrows()
            if "finansal rapor" in str(row.get("Title") or "").casefold()
        ][: args.financial_filing_limit]
        for row in financial_rows:
            title = str(row.get("Title") or "")
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
            "kap_history_source": kap_history_source,
            "kap_history_limit": args.kap_limit,
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
    print(f"KAP geçmiş kaynağı: {kap_history_source} · satır={len(news)}")
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
