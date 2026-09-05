from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Sequence

import pandas as pd

from ..fundamental_models import FinancialSnapshot, SectorType, StatementType
from .kap_metadata import KapFilingMetadata


@dataclass(frozen=True)
class CanonicalRowMap:
    balance_sheet: Mapping[str, Sequence[str]] = field(default_factory=dict)
    income_statement: Mapping[str, Sequence[str]] = field(default_factory=dict)
    cash_flow: Mapping[str, Sequence[str]] = field(default_factory=dict)


def _normalize_label(value: object) -> str:
    text = str(value or "").strip().casefold()
    translation = str.maketrans("çğıöşü", "cgiosu")
    text = text.translate(translation)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def period_column(period_end: datetime, *, annual: bool) -> str:
    if annual:
        return str(period_end.year)
    quarter = (period_end.month - 1) // 3 + 1
    return f"{period_end.year}Q{quarter}"


def _index_lookup(frame: pd.DataFrame) -> dict[str, object]:
    lookup: dict[str, object] = {}
    for label in frame.index:
        normalized = _normalize_label(label)
        if normalized and normalized not in lookup:
            lookup[normalized] = label
    return lookup


def _extract_block(
    frame: pd.DataFrame,
    *,
    column: str,
    aliases: Mapping[str, Sequence[str]],
) -> tuple[dict[str, float | None], dict[str, str], list[str]]:
    if column not in frame.columns:
        raise ValueError(f"Finansal tablo sütunu bulunamadı: {column}")
    lookup = _index_lookup(frame)
    values: dict[str, float | None] = {}
    matched_rows: dict[str, str] = {}
    missing: list[str] = []
    for canonical, candidates in aliases.items():
        chosen = None
        for candidate in candidates:
            label = lookup.get(_normalize_label(candidate))
            if label is not None:
                chosen = label
                break
        if chosen is None:
            values[canonical] = None
            missing.append(canonical)
            continue
        raw = pd.to_numeric(pd.Series([frame.at[chosen, column]]), errors="coerce").iloc[0]
        values[canonical] = None if pd.isna(raw) else float(raw)
        matched_rows[canonical] = str(chosen)
        if values[canonical] is None:
            missing.append(canonical)
    return values, matched_rows, missing


def build_snapshot_from_borsapy_tables(
    *,
    symbol: str,
    sector_type: SectorType,
    filing: KapFilingMetadata,
    balance_sheet: pd.DataFrame,
    income_statement: pd.DataFrame,
    cash_flow: pd.DataFrame,
    row_map: CanonicalRowMap,
    value_scale: float,
    shares_outstanding: float | None,
    financial_group: str,
    inflation_accounting: str | None,
    flow_basis: str | None,
    audit_status: str | None = None,
    extra_metadata: Mapping[str, object] | None = None,
) -> FinancialSnapshot:
    """Pair explicit-period İş Yatırım values with exact KAP filing metadata.

    No period or publication date is invented. The caller must also provide the
    numeric scale of the İş Yatırım table explicitly; the adapter never guesses
    whether values are TL, thousands or millions. Row matching uses only an
    explicit alias map, so a changed provider label becomes a visible missing
    field instead of silently mapping to the wrong accounting concept.
    """
    if filing.published_at is None:
        raise ValueError("KAP published_at olmadan canonical snapshot üretilemez.")
    if filing.period_end is None:
        raise ValueError("KAP period_end olmadan canonical snapshot üretilemez.")
    if value_scale <= 0:
        raise ValueError("value_scale pozitif olmalıdır.")
    if filing.currency is None:
        raise ValueError("KAP sunum para birimi bilinmeden snapshot üretilemez.")

    annual = bool(
        filing.period_label
        and ("yıll" in filing.period_label.casefold() or "12 ayl" in filing.period_label.casefold())
    )
    column = period_column(filing.period_end, annual=annual)
    balance, matched_balance, missing_balance = _extract_block(
        balance_sheet,
        column=column,
        aliases=row_map.balance_sheet,
    )
    income, matched_income, missing_income = _extract_block(
        income_statement,
        column=column,
        aliases=row_map.income_statement,
    )
    cash, matched_cash, missing_cash = _extract_block(
        cash_flow,
        column=column,
        aliases=row_map.cash_flow,
    )

    metadata: dict[str, object] = {
        "financial_group": financial_group,
        "provider_period_column": column,
        "provider_value_scale": value_scale,
        "kap_disclosure_id": filing.disclosure_id,
        "kap_url": filing.url,
        "kap_period_label": filing.period_label,
        "kap_period_end_source": filing.quality.get("period_end_source"),
        "consolidation": filing.consolidation,
        "row_matches": {
            "balance_sheet": matched_balance,
            "income_statement": matched_income,
            "cash_flow": matched_cash,
        },
        "missing_canonical_rows": {
            "balance_sheet": missing_balance,
            "income_statement": missing_income,
            "cash_flow": missing_cash,
        },
    }
    if flow_basis:
        metadata["flow_basis"] = flow_basis
    if extra_metadata:
        metadata.update(dict(extra_metadata))

    return FinancialSnapshot(
        symbol=symbol.strip().upper(),
        sector_type=sector_type,
        period_end=filing.period_end,
        published_at=filing.published_at,
        currency=filing.currency,
        scale=value_scale,
        statement_type=StatementType.ANNUAL if annual else StatementType.QUARTERLY,
        audit_status=audit_status,
        inflation_accounting=inflation_accounting,
        source="borsapy/IsYatirim+KAP",
        income_statement=income,
        balance_sheet=balance,
        cash_flow=cash,
        shares_outstanding=shares_outstanding,
        metadata=metadata,
    )
