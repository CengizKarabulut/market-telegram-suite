"""External fundamental-data adapters.

Provider-specific parsing lives here; valuation and accounting logic remains in
``market_core`` and only consumes canonical snapshots.
"""

from .borsapy_adapter import (
    CanonicalPeriodValues,
    CanonicalRowMap,
    RowSelector,
    build_snapshot_from_borsapy_tables,
    extract_canonical_period_values,
)
from .isyatirim_maps import (
    ISYATIRIM_XI29_GENERAL_ROW_MAP,
    ISYATIRIM_XI29_GYO_ROW_MAP,
)
from .kap_metadata import KapFilingMetadata, parse_kap_financial_report_html

__all__ = [
    "CanonicalPeriodValues",
    "CanonicalRowMap",
    "ISYATIRIM_XI29_GENERAL_ROW_MAP",
    "ISYATIRIM_XI29_GYO_ROW_MAP",
    "KapFilingMetadata",
    "RowSelector",
    "build_snapshot_from_borsapy_tables",
    "extract_canonical_period_values",
    "parse_kap_financial_report_html",
]
