from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping, Sequence, TypeAlias

import pandas as pd

from ..fundamental_models import FinancialSnapshot, SectorType, StatementType
from .kap_metadata import KapFilingMetadata


AggregateMode = Literal["SUM_DISTINCT_ROWS"]


@dataclass(frozen=True)
class RowSelector:
    """Explicitly select one or more provider rows for a canonical concept.

    İş Yatırım can expose the same visible label more than once (for example
    short- and long-term ``Finansal Borçlar``). It can also duplicate the same
    row when multiple API batches are joined. ``occurrence`` is evaluated after
    exact duplicate row-vectors are collapsed, while ``SUM_DISTINCT_ROWS`` sums
    each distinct row-vector once. This keeps duplicate API batches from
    double-counting debt without silently guessing between genuinely different
    accounting rows.
    """

    aliases: Sequence[str]
    occurrence: int | None = None
    aggregate: AggregateMode | None = None
    multiplier: float = 1.0

    def __post_init__(self) -> None:
        if not self.aliases:
            raise ValueError("RowSelector.aliases boş olamaz.")
        if self.occurrence is not None and self.occurrence < 0:
            raise ValueError("RowSelector.occurrence negatif olamaz.")
        if self.occurrence is not None and self.aggregate is not None:
            raise ValueError("occurrence ve aggregate aynı anda kullanılamaz.")
        if not math.isfinite(float(self.multiplier)):
            raise ValueError("RowSelector.multiplier sonlu olmalıdır.")


RowSpec: TypeAlias = Sequence[str] | RowSelector


@dataclass(frozen=True)
class CanonicalRowMap:
    balance_sheet: Mapping[str, RowSpec] = field(default_factory=dict)
    income_statement: Mapping[str, RowSpec] = field(default_factory=dict)
    cash_flow: Mapping[str, RowSpec] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalPeriodValues:
    """Canonical values extracted from one explicit provider period column.

    This object is intentionally *not* a FinancialSnapshot: a provider
    comparative column may be visible today without having a separately proven
    historical ``published_at``. It can therefore support current-report YoY
    context, but it must never be inserted into point-in-time backtests as if it
    were an independently published historical filing.
    """

    column: str
    balance_sheet: dict[str, float | None]
    income_statement: dict[str, float | None]
    cash_flow: dict[str, float | None]
    row_matches: dict[str, dict[str, object]]
    missing_canonical_rows: dict[str, list[str]]
    ambiguous_canonical_rows: dict[str, dict[str, object]]
    basis: str = "EXPLICIT_PROVIDER_PERIOD_COLUMN"


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


def _positions_by_label(frame: pd.DataFrame) -> dict[str, list[int]]:
    lookup: dict[str, list[int]] = {}
    for position, label in enumerate(frame.index):
        normalized = _normalize_label(label)
        if normalized:
            lookup.setdefault(normalized, []).append(position)
    return lookup


def _signature_value(value: object) -> object:
    if pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return number if math.isfinite(number) else None


def _row_signature(frame: pd.DataFrame, position: int) -> tuple[object, ...]:
    return tuple(_signature_value(value) for value in frame.iloc[position].tolist())


def _distinct_positions(frame: pd.DataFrame, positions: Sequence[int]) -> list[int]:
    distinct: list[int] = []
    seen: set[tuple[object, ...]] = set()
    for position in positions:
        signature = _row_signature(frame, position)
        if signature in seen:
            continue
        seen.add(signature)
        distinct.append(position)
    return distinct


def _selector(spec: RowSpec) -> RowSelector:
    if isinstance(spec, RowSelector):
        return spec
    if isinstance(spec, str):
        return RowSelector(aliases=(spec,))
    return RowSelector(aliases=tuple(spec))


def _candidate_positions(
    frame: pd.DataFrame,
    lookup: Mapping[str, list[int]],
    aliases: Sequence[str],
) -> tuple[str | None, list[int]]:
    for alias in aliases:
        positions = lookup.get(_normalize_label(alias), [])
        if positions:
            return alias, _distinct_positions(frame, positions)
    return None, []


def _numeric_at(frame: pd.DataFrame, position: int, column: str) -> float | None:
    raw = pd.to_numeric(pd.Series([frame.iloc[position][column]]), errors="coerce").iloc[0]
    return None if pd.isna(raw) else float(raw)


def _extract_block(
    frame: pd.DataFrame,
    *,
    column: str,
    aliases: Mapping[str, RowSpec],
) -> tuple[
    dict[str, float | None],
    dict[str, object],
    list[str],
    dict[str, object],
]:
    if column not in frame.columns:
        raise ValueError(f"Finansal tablo sütunu bulunamadı: {column}")
    lookup = _positions_by_label(frame)
    values: dict[str, float | None] = {}
    matched_rows: dict[str, object] = {}
    missing: list[str] = []
    ambiguous: dict[str, object] = {}

    for canonical, raw_spec in aliases.items():
        spec = _selector(raw_spec)
        alias, positions = _candidate_positions(frame, lookup, spec.aliases)
        if alias is None or not positions:
            values[canonical] = None
            missing.append(canonical)
            continue

        selected: list[int]
        if spec.aggregate == "SUM_DISTINCT_ROWS":
            selected = positions
        elif spec.occurrence is not None:
            if spec.occurrence >= len(positions):
                values[canonical] = None
                missing.append(canonical)
                ambiguous[canonical] = {
                    "reason": "OCCURRENCE_OUT_OF_RANGE",
                    "alias": alias,
                    "distinct_count": len(positions),
                    "requested_occurrence": spec.occurrence,
                }
                continue
            selected = [positions[spec.occurrence]]
        elif len(positions) == 1:
            selected = positions
        else:
            values[canonical] = None
            missing.append(canonical)
            ambiguous[canonical] = {
                "reason": "MULTIPLE_DISTINCT_PROVIDER_ROWS",
                "alias": alias,
                "distinct_count": len(positions),
                "positions": positions,
            }
            continue

        numeric_values = [_numeric_at(frame, position, column) for position in selected]
        if any(value is None for value in numeric_values):
            values[canonical] = None
            missing.append(canonical)
            continue
        assert all(value is not None for value in numeric_values)
        if spec.aggregate == "SUM_DISTINCT_ROWS":
            value = sum(float(item) for item in numeric_values)
        else:
            value = float(numeric_values[0])
        values[canonical] = value * float(spec.multiplier)
        matched_rows[canonical] = {
            "alias": alias,
            "positions": selected,
            "labels": [str(frame.index[position]) for position in selected],
            "aggregate": spec.aggregate,
            "multiplier": spec.multiplier,
            "provider_batch_duplicates_collapsed": len(
                [
                    position
                    for position in lookup.get(_normalize_label(alias), [])
                    if position not in positions
                ]
            ),
        }

    return values, matched_rows, missing, ambiguous


def extract_canonical_period_values(
    *,
    column: str,
    balance_sheet: pd.DataFrame,
    income_statement: pd.DataFrame,
    cash_flow: pd.DataFrame,
    row_map: CanonicalRowMap,
    basis: str = "EXPLICIT_PROVIDER_PERIOD_COLUMN",
) -> CanonicalPeriodValues:
    """Extract one named provider column without inventing publication metadata."""
    balance, matched_balance, missing_balance, ambiguous_balance = _extract_block(
        balance_sheet,
        column=column,
        aliases=row_map.balance_sheet,
    )
    income, matched_income, missing_income, ambiguous_income = _extract_block(
        income_statement,
        column=column,
        aliases=row_map.income_statement,
    )
    cash, matched_cash, missing_cash, ambiguous_cash = _extract_block(
        cash_flow,
        column=column,
        aliases=row_map.cash_flow,
    )
    return CanonicalPeriodValues(
        column=column,
        balance_sheet=balance,
        income_statement=income,
        cash_flow=cash,
        row_matches={
            "balance_sheet": matched_balance,
            "income_statement": matched_income,
            "cash_flow": matched_cash,
        },
        missing_canonical_rows={
            "balance_sheet": missing_balance,
            "income_statement": missing_income,
            "cash_flow": missing_cash,
        },
        ambiguous_canonical_rows={
            "balance_sheet": ambiguous_balance,
            "income_statement": ambiguous_income,
            "cash_flow": ambiguous_cash,
        },
        basis=basis,
    )


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
    explicit alias/selector map. Ambiguous duplicate labels therefore become a
    visible missing field unless the map states exactly how to select/aggregate
    them.
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
    period_values = extract_canonical_period_values(
        column=column,
        balance_sheet=balance_sheet,
        income_statement=income_statement,
        cash_flow=cash_flow,
        row_map=row_map,
        basis="KAP_LINKED_PROVIDER_PERIOD",
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
        "row_matches": period_values.row_matches,
        "missing_canonical_rows": period_values.missing_canonical_rows,
        "ambiguous_canonical_rows": period_values.ambiguous_canonical_rows,
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
        income_statement=period_values.income_statement,
        balance_sheet=period_values.balance_sheet,
        cash_flow=period_values.cash_flow,
        shares_outstanding=shares_outstanding,
        metadata=metadata,
    )
