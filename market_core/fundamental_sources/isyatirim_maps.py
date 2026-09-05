"""Explicit İş Yatırım row maps for canonical fundamental snapshots.

These maps are deliberately conservative. A provider row is mapped only when
its accounting meaning is sufficiently clear from the published label. Metrics
that require a more granular KAP note remain unavailable instead of being
approximated from broader summary rows.
"""

from .borsapy_adapter import CanonicalRowMap, RowSelector


_COMMON_BALANCE = {
    "cash_and_equivalents": (
        "Nakit ve Nakit Benzerleri",
        "Nakit ve Nakit Benzerleri ",
    ),
    "current_assets": ("Dönen Varlıklar",),
    "total_assets": ("TOPLAM VARLIKLAR",),
    "current_liabilities": ("Kısa Vadeli Yükümlülükler",),
    "equity": ("Özkaynaklar",),
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
}

_COMMON_INCOME = {
    "revenue": ("Satış Gelirleri",),
    "gross_profit": ("BRÜT KAR (ZARAR)",),
    "net_operating_profit": ("Net Faaliyet Kar/Zararı",),
    "other_operating_income": ("Diğer Faaliyet Gelirleri",),
    "ebit": ("FAALİYET KARI (ZARARI)",),
    "profit_before_tax": (
        "SÜRDÜRÜLEN FAALİYETLER VERGİ ÖNCESİ KARI (ZARARI)",
    ),
    "tax_expense": RowSelector(
        aliases=("Sürdürülen Faaliyetler Vergi Geliri (Gideri)",),
        multiplier=-1.0,
    ),
    "net_income": ("DÖNEM KARI (ZARARI)",),
}

_COMMON_CASH_FLOW = {
    "operating_cash_flow": (
        "İşletme Faaliyetlerinden Kaynaklanan Net Nakit",
    ),
}


ISYATIRIM_XI29_GENERAL_ROW_MAP = CanonicalRowMap(
    balance_sheet=_COMMON_BALANCE,
    income_statement=_COMMON_INCOME,
    cash_flow=_COMMON_CASH_FLOW,
)


ISYATIRIM_XI29_GYO_ROW_MAP = CanonicalRowMap(
    balance_sheet={
        **_COMMON_BALANCE,
        "investment_property_fair_value": ("Yatırım Amaçlı Gayrimenkuller",),
    },
    income_statement=_COMMON_INCOME,
    cash_flow=_COMMON_CASH_FLOW,
)


__all__ = [
    "ISYATIRIM_XI29_GENERAL_ROW_MAP",
    "ISYATIRIM_XI29_GYO_ROW_MAP",
]
