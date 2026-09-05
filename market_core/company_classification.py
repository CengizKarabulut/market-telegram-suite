from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from .fundamental_models import SectorType


@dataclass(frozen=True)
class CompanyClassification:
    symbol: str
    sector_type: SectorType
    sector: str | None
    industry: str | None
    peer_group: str
    source: str
    confidence: str
    metadata: Mapping[str, Any]


def _clean(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _fold(value: object) -> str:
    text = str(value or "").translate(str.maketrans({"ı": "i", "İ": "I"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _slug(value: object) -> str:
    text = _fold(value)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_").upper()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def classify_company(
    *,
    symbol: str,
    sector: str | None,
    industry: str | None,
    source: str = "provider_info",
    explicit_sector_type: SectorType | None = None,
    explicit_peer_group: str | None = None,
) -> CompanyClassification:
    """Map provider company metadata to an accounting archetype and peer group.

    ``sector_type`` controls which accounting/valuation family is safe to use.
    ``peer_group`` is intentionally more granular and normally follows provider
    ``industry`` so a retailer is not benchmarked against an airline merely
    because both are non-financial companies.
    """
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol boş olamaz")

    sector_clean = _clean(sector)
    industry_clean = _clean(industry)
    combined = _fold(" ".join(item for item in (sector_clean, industry_clean) if item))

    if explicit_sector_type is not None:
        sector_type = explicit_sector_type
        confidence = "EXPLICIT"
        archetype_reason = "explicit_override"
    elif _contains_any(
        combined,
        (
            "gayrimenkul yatirim ortakligi",
            "gayrimenkul yatirim ortakliklari",
            "real estate investment trust",
            "reit",
        ),
    ):
        sector_type = SectorType.GYO
        confidence = "HIGH"
        archetype_reason = "real_estate_investment_trust_match"
    elif _contains_any(
        combined,
        (
            "banka",
            "bankacilik",
            "banking",
            "banks",
            "major banks",
            "regional banks",
            "savings banks",
        ),
    ):
        sector_type = SectorType.BANK
        confidence = "HIGH"
        archetype_reason = "bank_match"
    elif _contains_any(
        combined,
        (
            "holding",
            "investment holding",
            "financial conglomerates",
        ),
    ):
        sector_type = SectorType.HOLDING
        confidence = "HIGH"
        archetype_reason = "holding_match"
    elif _contains_any(
        combined,
        (
            "sigorta",
            "insurance",
            "emeklilik",
            "pension",
            "multi line insurance",
            "property casualty insurance",
            "life health insurance",
            "specialty insurers",
        ),
    ):
        sector_type = SectorType.INSURANCE
        confidence = "HIGH"
        archetype_reason = "insurance_match"
    elif _contains_any(
        combined,
        (
            "finansal kiralama",
            "leasing",
            "faktoring",
            "factoring",
            "araci kurum",
            "brokerage",
            "investment banks brokers",
            "menkul deger",
            "portfoy yonetim",
            "asset management",
            "investment managers",
            "consumer finance",
            "finance rental leasing",
            "finansman sirket",
        ),
    ):
        sector_type = SectorType.FINANCIAL_NONBANK
        confidence = "HIGH"
        archetype_reason = "nonbank_financial_match"
    elif sector_clean or industry_clean:
        sector_type = SectorType.INDUSTRIAL
        confidence = "MEDIUM"
        archetype_reason = "generic_nonfinancial_fallback"
    else:
        sector_type = SectorType.OTHER
        confidence = "LOW"
        archetype_reason = "metadata_missing"

    if explicit_peer_group:
        peer_group = explicit_peer_group.strip().upper()
        peer_group_source = "explicit_override"
    elif industry_clean:
        peer_group = f"INDUSTRY_{_slug(industry_clean)}"
        peer_group_source = "provider_industry"
    elif sector_clean:
        peer_group = f"SECTOR_{_slug(sector_clean)}"
        peer_group_source = "provider_sector"
    else:
        peer_group = f"ARCHETYPE_{sector_type.value}"
        peer_group_source = "analysis_archetype_fallback"

    return CompanyClassification(
        symbol=normalized_symbol,
        sector_type=sector_type,
        sector=sector_clean,
        industry=industry_clean,
        peer_group=peer_group,
        source=source,
        confidence=confidence,
        metadata={
            "archetype_reason": archetype_reason,
            "peer_group_source": peer_group_source,
            "sector_type_is_not_peer_group": True,
            "provider_sector": sector_clean,
            "provider_industry": industry_clean,
        },
    )


__all__ = ["CompanyClassification", "classify_company"]
