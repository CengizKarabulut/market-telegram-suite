"""Explicit İş Yatırım row maps for canonical fundamental snapshots.

These maps are deliberately conservative. A provider row is mapped only when
its accounting meaning is sufficiently clear from the published label. Metrics
that require a more granular KAP note (for example rental-only revenue or the
investment-property fair-value gain itself) remain unavailable instead of being
approximated from a broader summary row.
"""

from .borsapy_adapter import CanonicalRowMap, RowSelector


ISYATIRIM_XI29_GYO_ROW_MAP = CanonicalRowMap(
    balance_sheet={
        "cash_and_equivalents": (
            "Nakit ve Nakit Benzerleri",
            "Nakit ve Nakit Benzerleri ",
        ),
        "current_assets": ("Dönen Varlıklar",),
        "total_assets": ("TOPLAM VARLIKLAR",),
        "current_liabilities": ("Kısa Vadeli Yükümlülükler",),
        "equity": ("Özkaynaklar",),
        "investment_property_fair_value": ("Yatırım Amaçlı Gayrimenkuller",),
        "short_term_financial_debt": RowSelector(
            aliases=("Finansal Borçlar",),
            occurrence=0,
        ),
        "long_term_financial_debt": RowSelector(
            aliases=("Finansal Borçlar",),
            occurrence=1,
        ),
        "total_financial_debt": RowSelector(
            aliases=("Finansal Borçlar",),
            aggregate="SUM_DISTINCT_ROWS",
        ),
    },
    income_statement={
        "revenue": ("Satış Gelirleri",),
        "gross_profit": ("BRÜT KAR (ZARAR)",),
        "ebit": ("FAALİYET KARI (ZARARI)",),
        "profit_before_tax": (
            "SÜRDÜRÜLEN FAALİYETLER VERGİ ÖNCESİ KARI (ZARARI)",
        ),
        "tax_expense": RowSelector(
            aliases=("Sürdürülen Faaliyetler Vergi Geliri (Gideri)",),
            multiplier=-1.0,
        ),
        "net_income": ("DÖNEM KARI (ZARARI)",),
    },
    cash_flow={
        "operating_cash_flow": (
            "İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
        ),
    },
)


__all__ = ["ISYATIRIM_XI29_GYO_ROW_MAP"]
