from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SectorType(str, Enum):
    INDUSTRIAL = "INDUSTRIAL"
    GYO = "GYO"
    BANK = "BANK"
    HOLDING = "HOLDING"
    INSURANCE = "INSURANCE"
    FINANCIAL_NONBANK = "FINANCIAL_NONBANK"
    OTHER = "OTHER"


class StatementType(str, Enum):
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"
    OTHER = "OTHER"


@dataclass(frozen=True)
class FinancialSnapshot:
    symbol: str
    sector_type: SectorType
    period_end: datetime
    published_at: datetime
    currency: str
    scale: float
    statement_type: StatementType = StatementType.OTHER
    audit_status: str | None = None
    inflation_accounting: str | None = None
    restatement_id: str | None = None
    source: str | None = None
    income_statement: dict[str, float | None] = field(default_factory=dict)
    balance_sheet: dict[str, float | None] = field(default_factory=dict)
    cash_flow: dict[str, float | None] = field(default_factory=dict)
    shares_outstanding: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("FinancialSnapshot symbol boş olamaz.")
        if not self.currency.strip():
            raise ValueError("FinancialSnapshot currency boş olamaz.")
        if self.scale <= 0:
            raise ValueError("FinancialSnapshot scale pozitif olmalıdır.")
        if self.published_at.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError("FinancialSnapshot tarihleri timezone-aware olmalıdır.")
        if self.shares_outstanding is not None and self.shares_outstanding <= 0:
            raise ValueError("shares_outstanding verilmişse pozitif olmalıdır.")


@dataclass(frozen=True)
class PointInTimeSelection:
    as_of: datetime
    snapshot: FinancialSnapshot | None
    available_count: int
    excluded_future_count: int
    reason: str | None = None
