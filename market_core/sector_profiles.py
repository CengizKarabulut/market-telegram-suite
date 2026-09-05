from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

from .fundamental_models import SectorType


MetricDirection = Literal["HIGHER_BETTER", "LOWER_BETTER", "CONTEXTUAL"]


@dataclass(frozen=True)
class SectorMetricRule:
    metric: str
    label: str
    direction: MetricDirection
    unit: str = "ratio"
    minimum_peers: int = 4


@dataclass(frozen=True)
class SectorProfile:
    code: str
    label: str
    metric_rules: tuple[SectorMetricRule, ...]
    notes: tuple[str, ...] = ()


def _rule(
    metric: str,
    label: str,
    direction: MetricDirection,
    *,
    unit: str = "ratio",
    minimum_peers: int = 4,
) -> SectorMetricRule:
    return SectorMetricRule(
        metric=metric,
        label=label,
        direction=direction,
        unit=unit,
        minimum_peers=minimum_peers,
    )


GENERAL_PROFILE = SectorProfile(
    code="GENERAL",
    label="Genel şirket karşılaştırması",
    metric_rules=(
        _rule("revenue_growth", "Ciro büyümesi", "HIGHER_BETTER"),
        _rule("net_income_growth", "Net kâr büyümesi", "HIGHER_BETTER"),
        _rule("gross_margin", "Brüt kâr marjı", "HIGHER_BETTER"),
        _rule("ebitda_margin", "FAVÖK marjı", "HIGHER_BETTER"),
        _rule("net_margin", "Net kâr marjı", "HIGHER_BETTER"),
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule("roa", "Aktif kârlılığı", "HIGHER_BETTER"),
        _rule("roic", "Yatırılmış sermaye getirisi", "HIGHER_BETTER"),
        _rule("net_debt_to_ebitda", "Net borç/FAVÖK", "LOWER_BETTER"),
        _rule("interest_coverage", "Faiz karşılama", "HIGHER_BETTER"),
        _rule(
            "operating_cash_flow_to_net_income",
            "Nakit dönüşümü",
            "HIGHER_BETTER",
        ),
        _rule("pe", "F/K", "CONTEXTUAL"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
        _rule("ev_to_ebitda", "FD/FAVÖK", "CONTEXTUAL"),
        _rule("price_to_sales", "Fiyat/satışlar", "CONTEXTUAL"),
    ),
    notes=(
        "Genel profil yalnızca aynı iş modeli için daha özel profil bulunamadığında kullanılır.",
        "Çarpanların sektör medyanının altında olması otomatik olarak ucuzluk anlamına gelmez; büyüme, kârlılık ve bilanço kalitesiyle birlikte okunur.",
    ),
)


GYO_PROFILE = SectorProfile(
    code="GYO",
    label="Gayrimenkul Yatırım Ortaklığı",
    metric_rules=(
        _rule("ltv", "Kredi/değer oranı (LTV)", "LOWER_BETTER"),
        _rule("rental_revenue_share", "Kira gelirlerinin payı", "HIGHER_BETTER"),
        _rule(
            "fair_value_gain_share_of_pretax",
            "Değerleme kazancının vergi öncesi kârdaki payı",
            "LOWER_BETTER",
        ),
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule(
            "operating_cash_flow_to_net_income",
            "Nakit dönüşümü",
            "HIGHER_BETTER",
        ),
        _rule("price_to_nav", "Fiyat/NAD", "CONTEXTUAL"),
        _rule("nav_discount", "NAD iskontosu", "CONTEXTUAL"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
    ),
    notes=(
        "GYO karşılaştırmasında düşük LTV tek başına yeterli değildir; kira üretimi, nakit dönüşümü ve NAD birlikte değerlendirilir.",
        "Değerleme kazancı yüksekliği doğrudan kötü sayılmaz; sürdürülebilir faaliyet gelirinin yerini ne ölçüde aldığı ayrıca yorumlanır.",
        "NAD güvenilir biçimde bulunamıyorsa fiyat/defter yalnız ikincil, bağlamsal bir karşılaştırma olarak kullanılır.",
    ),
)


BANK_PROFILE = SectorProfile(
    code="BANK",
    label="Banka",
    metric_rules=(
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule("roa", "Aktif kârlılığı", "HIGHER_BETTER"),
        _rule("net_interest_margin", "Net faiz marjı", "HIGHER_BETTER"),
        _rule("capital_adequacy_ratio", "Sermaye yeterlilik oranı", "HIGHER_BETTER"),
        _rule("npl_ratio", "Takipteki kredi oranı", "LOWER_BETTER"),
        _rule("cost_to_income", "Maliyet/gelir oranı", "LOWER_BETTER"),
        _rule("loan_to_deposit", "Kredi/mevduat oranı", "CONTEXTUAL"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
        _rule("pe", "F/K", "CONTEXTUAL"),
    ),
    notes=(
        "Bankalarda sanayi şirketlerine ait net borç/FAVÖK gibi oranlar kullanılmaz.",
    ),
)


INSURANCE_PROFILE = SectorProfile(
    code="INSURANCE",
    label="Sigorta / emeklilik",
    metric_rules=(
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule("premium_growth", "Prim üretimi büyümesi", "HIGHER_BETTER"),
        _rule("combined_ratio", "Bileşik rasyo", "LOWER_BETTER"),
        _rule("loss_ratio", "Hasar/prim oranı", "LOWER_BETTER"),
        _rule("solvency_ratio", "Sermaye yeterlilik/solvency oranı", "HIGHER_BETTER"),
        _rule("investment_income_share", "Yatırım gelirlerinin kârdaki payı", "CONTEXTUAL"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
        _rule("pe", "F/K", "CONTEXTUAL"),
    ),
    notes=(
        "Sigorta şirketlerinde net borç/FAVÖK ve sanayi tipi işletme sermayesi oranları temel kıyas değildir.",
    ),
)


FINANCIAL_NONBANK_PROFILE = SectorProfile(
    code="FINANCIAL_NONBANK",
    label="Banka dışı finansal kuruluş",
    metric_rules=(
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule("roa", "Aktif kârlılığı", "HIGHER_BETTER"),
        _rule("net_interest_margin", "Net faiz/finansman marjı", "HIGHER_BETTER"),
        _rule("cost_to_income", "Maliyet/gelir oranı", "LOWER_BETTER"),
        _rule("npl_ratio", "Takipteki alacak oranı", "LOWER_BETTER"),
        _rule("capital_adequacy_ratio", "Sermaye yeterlilik oranı", "HIGHER_BETTER"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
        _rule("pe", "F/K", "CONTEXTUAL"),
    ),
    notes=(
        "Aracı kurum, finansal kiralama, faktoring ve benzeri şirketlerde iş modeline özel alt grup mümkün olduğunda geniş finansal sektör ortalaması yerine o grup kullanılmalıdır.",
    ),
)


HOLDING_PROFILE = SectorProfile(
    code="HOLDING",
    label="Holding",
    metric_rules=(
        _rule("nav_discount", "NAD iskontosu", "CONTEXTUAL"),
        _rule("holding_net_debt_to_nav", "Holding net borç/NAD", "LOWER_BETTER"),
        _rule("roe", "Özkaynak kârlılığı", "HIGHER_BETTER"),
        _rule("cash_dividend_income_share", "Temettü gelir payı", "CONTEXTUAL"),
        _rule("price_to_book", "Fiyat/defter değeri", "CONTEXTUAL"),
        _rule("pe", "F/K", "CONTEXTUAL"),
    ),
    notes=(
        "Holdinglerde konsolide FAVÖK tek başına ekonomik borçluluğu temsil etmeyebilir; holding-seviyesi net borç tercih edilir.",
    ),
)


INDUSTRIAL_PROFILE = SectorProfile(
    code="INDUSTRIAL",
    label="Sanayi / hizmet şirketi",
    metric_rules=GENERAL_PROFILE.metric_rules,
)


SECTOR_PROFILES: Mapping[SectorType, SectorProfile] = {
    SectorType.GYO: GYO_PROFILE,
    SectorType.BANK: BANK_PROFILE,
    SectorType.HOLDING: HOLDING_PROFILE,
    SectorType.INSURANCE: INSURANCE_PROFILE,
    SectorType.FINANCIAL_NONBANK: FINANCIAL_NONBANK_PROFILE,
    SectorType.INDUSTRIAL: INDUSTRIAL_PROFILE,
    SectorType.OTHER: GENERAL_PROFILE,
}


def profile_for_sector(sector_type: SectorType) -> SectorProfile:
    return SECTOR_PROFILES.get(sector_type, GENERAL_PROFILE)


__all__ = [
    "BANK_PROFILE",
    "FINANCIAL_NONBANK_PROFILE",
    "GENERAL_PROFILE",
    "GYO_PROFILE",
    "HOLDING_PROFILE",
    "INDUSTRIAL_PROFILE",
    "INSURANCE_PROFILE",
    "MetricDirection",
    "SectorMetricRule",
    "SectorProfile",
    "profile_for_sector",
]
