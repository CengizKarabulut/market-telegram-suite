"""External fundamental-data adapters.

Provider-specific parsing lives here; valuation and accounting logic remains in
``market_core`` and only consumes canonical snapshots.
"""

from .kap_metadata import KapFilingMetadata, parse_kap_financial_report_html

__all__ = ["KapFilingMetadata", "parse_kap_financial_report_html"]
