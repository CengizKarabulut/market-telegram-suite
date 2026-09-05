from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import borsapy as bp
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_core.company_classification import classify_company
from market_core.fundamental_models import SectorType
from market_core.fundamental_period import (
    PeriodComparative,
    build_current_period_fundamental_view,
)
from market_core.fundamental_sources import (
    ISYATIRIM_XI29_GENERAL_ROW_MAP,
    ISYATIRIM_XI29_GYO_ROW_MAP,
    build_snapshot_from_borsapy_tables,
    extract_canonical_period_values,
    parse_kap_financial_report_html,
)


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(value.value)
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
    try:
        provider_getter = getattr(ticker, "_get_kap", None)
        if callable(provider_getter):
            provider = provider_getter()
            get_disclosures = getattr(provider, "get_disclosures", None)
            if callable(get_disclosures):
                frame = get_disclosures(symbol, limit=limit)
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    return frame, "borsapy/KAP.get_disclosures"
    except Exception as exc:  # noqa: BLE001 - probe must fail soft on provider drift
        print(f"KAP derin geçmiş sorgusu kullanılamadı; Ticker.news fallback: {exc}")
    return ticker.news, "borsapy/Ticker.news_fallback"


def _safe_frame(label: str, loader: Callable[[], pd.DataFrame]) -> tuple[pd.DataFrame, str | None]:
    try:
        frame = loader()
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(), None
    except Exception as exc:  # noqa: BLE001 - probe records unsupported provider combinations
        message = f"{label} alınamadı: {exc}"
        print(message)
        return pd.DataFrame(), message


def _resolve_financial_group(requested: str, sector_type: SectorType) -> tuple[str, str]:
    cleaned = requested.strip().upper()
    if cleaned and cleaned != "AUTO":
        return cleaned, "explicit"
    if sector_type == SectorType.BANK:
        return "UFRS", "auto_bank_ufrs"
    return "XI_29", "auto_default_xi29"


def _prior_comparative_column(column: str) -> str | None:
    quarterly = re.fullmatch(r"(\d{4})Q([1-4])", column)
    if quarterly:
        return f"{int(quarterly.group(1)) - 1}Q{quarterly.group(2)}"
    annual = re.fullmatch(r"\d{4}", column)
    if annual:
        return str(int(column) - 1)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 çok sektörlü gerçek finansal veri probu")
    parser.add_argument("symbol")
    parser.add_argument("--last-n", type=int, default=8)
    parser.add_argument("--output", default="reports/v4_fundamental_probe")
    parser.add_argument("--financial-group", default="AUTO")
    parser.add_argument("--value-scale", type=float, default=1.0)
    parser.add_argument("--inflation-accounting", default=None)
    parser.add_argument("--kap-limit", type=int, default=120)
    parser.add_argument("--financial-filing-limit", type=int, default=16)
    args = parser.parse_args()

    if args.kap_limit < 20:
        parser.error("--kap-limit en az 20 olmalıdır")
    if args.financial_filing_limit < 1:
        parser.error("--financial-filing-limit en az 1 olmalıdır")
    if args.value_scale <= 0:
        parser.error("--value-scale pozitif olmalıdır")

    symbol = args.symbol.strip().upper().removesuffix(".IS").removesuffix(".E")
    target = Path(args.output) / symbol
    target.mkdir(parents=True, exist_ok=True)
    ticker = bp.Ticker(symbol)

    info: dict[str, Any] = {}
    info_error: str | None = None
    try:
        raw_info = ticker.info
        if isinstance(raw_info, dict):
            info = raw_info
    except Exception as exc:  # noqa: BLE001 - source probe records metadata failures
        info_error = str(exc)
        print(f"Şirket metadata'sı alınamadı: {exc}")

    classification = classify_company(
        symbol=symbol,
        sector=str(info.get("sector") or "") or None,
        industry=str(info.get("industry") or "") or None,
        source="borsapy/Ticker.info",
    )
    financial_group, financial_group_source = _resolve_financial_group(
        args.financial_group,
        classification.sector_type,
    )

    balance, balance_error = _safe_frame(
        "Çeyreklik bilanço",
        lambda: ticker.get_balance_sheet(
            quarterly=True,
            last_n=args.last_n,
            financial_group=financial_group,
        ),
    )
    income, income_error = _safe_frame(
        "Çeyreklik gelir tablosu",
        lambda: ticker.get_income_stmt(
            quarterly=True,
            last_n=args.last_n,
            financial_group=financial_group,
        ),
    )
    cashflow, cashflow_error = _safe_frame(
        "Çeyreklik nakit akış",
        lambda: ticker.get_cashflow(
            quarterly=True,
            last_n=args.last_n,
            financial_group=financial_group,
        ),
    )
    annual_balance, annual_balance_error = _safe_frame(
        "Yıllık bilanço",
        lambda: ticker.get_balance_sheet(
            quarterly=False,
            last_n=4,
            financial_group=financial_group,
        ),
    )
    annual_income, annual_income_error = _safe_frame(
        "Yıllık gelir tablosu",
        lambda: ticker.get_income_stmt(
            quarterly=False,
            last_n=4,
            financial_group=financial_group,
        ),
    )
    annual_cashflow, annual_cashflow_error = _safe_frame(
        "Yıllık nakit akış",
        lambda: ticker.get_cashflow(
            quarterly=False,
            last_n=4,
            financial_group=financial_group,
        ),
    )

    tables: dict[str, dict[str, Any]] = {}
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
    parsed_filings = []
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
            parsed_filings.append(parsed)
            item = asdict(parsed)
            item["news_date"] = str(row.get("Date") or "")
            financial_filings.append(item)

    current_analysis: dict[str, Any] = {
        "available": False,
        "reason": "Canonical current-period analysis not attempted.",
    }
    if financial_group == "XI_29" and parsed_filings:
        filing = next(
            (
                item
                for item in parsed_filings
                if item.period_end is not None and item.published_at is not None and item.currency
            ),
            None,
        )
        if filing is not None:
            is_annual = bool(
                filing.period_label
                and ("yıll" in filing.period_label.casefold() or "12 ayl" in filing.period_label.casefold())
            )
            source_balance = annual_balance if is_annual else balance
            source_income = annual_income if is_annual else income
            source_cashflow = annual_cashflow if is_annual else cashflow
            row_map = (
                ISYATIRIM_XI29_GYO_ROW_MAP
                if classification.sector_type == SectorType.GYO
                else ISYATIRIM_XI29_GENERAL_ROW_MAP
            )
            if not source_balance.empty and not source_income.empty and not source_cashflow.empty:
                snapshot = build_snapshot_from_borsapy_tables(
                    symbol=symbol,
                    sector_type=classification.sector_type,
                    filing=filing,
                    balance_sheet=source_balance,
                    income_statement=source_income,
                    cash_flow=source_cashflow,
                    row_map=row_map,
                    value_scale=args.value_scale,
                    shares_outstanding=None,
                    financial_group=financial_group,
                    inflation_accounting=args.inflation_accounting,
                    flow_basis=None,
                    extra_metadata={
                        "provider_sector": classification.sector,
                        "provider_industry": classification.industry,
                        "peer_group": classification.peer_group,
                    },
                )
                current_column = str(snapshot.metadata.get("provider_period_column") or "")
                prior_column = _prior_comparative_column(current_column)
                comparative = None
                if prior_column and all(
                    prior_column in frame.columns
                    for frame in (source_balance, source_income, source_cashflow)
                ):
                    prior = extract_canonical_period_values(
                        column=prior_column,
                        balance_sheet=source_balance,
                        income_statement=source_income,
                        cash_flow=source_cashflow,
                        row_map=row_map,
                        basis="CURRENT_PROVIDER_COMPARATIVE",
                    )
                    comparative = PeriodComparative(
                        label=prior_column,
                        currency=snapshot.currency,
                        scale=snapshot.scale,
                        basis=prior.basis,
                        income_statement=prior.income_statement,
                        balance_sheet=prior.balance_sheet,
                        cash_flow=prior.cash_flow,
                    )
                current_analysis = build_current_period_fundamental_view(
                    snapshot,
                    comparative=comparative,
                )
                current_analysis["classification"] = asdict(classification)
                current_analysis["snapshot_metadata"] = snapshot.metadata
                (target / "current_fundamental_view.json").write_text(
                    json.dumps(
                        current_analysis,
                        ensure_ascii=False,
                        indent=2,
                        default=_json_default,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            else:
                current_analysis = {
                    "available": False,
                    "reason": "XI_29 canonical analiz için gerekli tablo ailesinden biri boş.",
                }
    elif financial_group == "UFRS":
        current_analysis = {
            "available": False,
            "reason": "UFRS banka canonical row-map katmanı henüz eklenmedi; raw probe korunuyor.",
        }

    payload = {
        "symbol": symbol,
        "classification": asdict(classification),
        "company_info": {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "longBusinessSummary": info.get("longBusinessSummary"),
            "metadata_error": info_error,
        },
        "financial_group": financial_group,
        "financial_group_source": financial_group_source,
        "source_contract": {
            "financial_values": "borsapy/IsYatirim",
            "publication_metadata": "borsapy/KAP",
            "company_metadata": "borsapy/Ticker.info",
            "kap_history_source": kap_history_source,
            "kap_history_limit": args.kap_limit,
            "borsapy_ttm_used": False,
            "point_in_time_note": (
                "Provider TTM is not accepted as canonical; exact KAP published_at and "
                "accounting basis must be proven before TTM assembly."
            ),
        },
        "table_errors": {
            "balance_quarterly": balance_error,
            "income_quarterly": income_error,
            "cashflow_quarterly": cashflow_error,
            "balance_annual": annual_balance_error,
            "income_annual": annual_income_error,
            "cashflow_annual": annual_cashflow_error,
        },
        "tables": tables,
        "financial_filings": financial_filings,
        "current_analysis": current_analysis,
    }
    output = target / "probe.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    print(f"V4 fundamental probe: {symbol}")
    print(
        "Sınıflama: "
        f"{classification.sector_type.value} · peer={classification.peer_group} · "
        f"sector={classification.sector} · industry={classification.industry}"
    )
    print(f"Finansal grup: {financial_group} ({financial_group_source})")
    for name, meta in tables.items():
        print(f"{name}: {meta['shape']} · columns={meta['columns']}")
    print(f"KAP geçmiş kaynağı: {kap_history_source} · satır={len(news)}")
    print(f"KAP finansal rapor kaydı: {len(financial_filings)}")
    print(f"Cari canonical analiz: {current_analysis.get('available')}")
    if current_analysis.get("available"):
        synthesis = current_analysis.get("synthesis") or {}
        print(f"Cari temel sentez: {synthesis.get('state')} · {synthesis.get('headline')}")
    else:
        print(f"Cari analiz notu: {current_analysis.get('reason')}")
    print(f"Probe: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
