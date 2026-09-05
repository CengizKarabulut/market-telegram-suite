from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


ISTANBUL = ZoneInfo("Europe/Istanbul")


@dataclass(frozen=True)
class CorporateEvent:
    disclosure_id: int | None
    published_at: datetime | None
    title: str
    category: str
    category_label: str
    direction: str
    materiality: str
    url: str | None
    source: str
    quality: Mapping[str, Any]


_CATEGORY_LABELS = {
    "FINANCIAL_REPORT": "Finansal rapor / sonuç",
    "DIVIDEND": "Temettü / kâr payı",
    "BUYBACK": "Pay geri alımı",
    "CAPITAL_ACTION": "Sermaye işlemi",
    "CONTRACT_ORDER": "Sözleşme / sipariş / ihale",
    "INVESTMENT_CAPEX": "Yatırım / kapasite / tesis",
    "MNA": "Birleşme / satın alma / ortaklık",
    "ASSET_TRANSACTION": "Varlık alım-satımı",
    "FINANCING_DEBT": "Finansman / borçlanma",
    "CREDIT_RATING": "Kredi derecelendirme",
    "LEGAL_REGULATORY": "Hukuki / düzenleyici gelişme",
    "GOVERNANCE": "Yönetim / genel kurul / kurumsal yönetim",
    "OPERATIONAL": "Operasyonel gelişme",
    "OTHER": "Diğer özel durum açıklaması",
}

_CATEGORY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "FINANCIAL_REPORT",
        (
            "finansal rapor",
            "finansal tablo",
            "faaliyet raporu",
            "financial report",
            "financial statements",
        ),
    ),
    (
        "DIVIDEND",
        (
            "kar payi",
            "temettu",
            "dividend",
            "kar dagitim",
        ),
    ),
    (
        "BUYBACK",
        (
            "pay geri alim",
            "geri alim program",
            "share buyback",
            "repurchase",
        ),
    ),
    (
        "CAPITAL_ACTION",
        (
            "sermaye artirim",
            "sermaye azalt",
            "bedelli",
            "bedelsiz",
            "capital increase",
            "capital decrease",
            "rights issue",
        ),
    ),
    (
        "CONTRACT_ORDER",
        (
            "sozlesme",
            "siparis",
            "ihale",
            "contract",
            "order",
            "tender",
        ),
    ),
    (
        "INVESTMENT_CAPEX",
        (
            "yatirim",
            "kapasite art",
            "tesis",
            "fabrika",
            "uretim hatti",
            "investment",
            "capacity",
            "plant",
        ),
    ),
    (
        "MNA",
        (
            "birlesme",
            "devralma",
            "satin alma",
            "ortaklik gorus",
            "merger",
            "acquisition",
            "joint venture",
        ),
    ),
    (
        "ASSET_TRANSACTION",
        (
            "varlik satis",
            "varlik alim",
            "gayrimenkul satis",
            "gayrimenkul alim",
            "asset sale",
            "asset purchase",
        ),
    ),
    (
        "FINANCING_DEBT",
        (
            "borclanma araci",
            "kredi sozles",
            "finansman",
            "tahvil",
            "bono",
            "bond issuance",
            "financing",
            "loan agreement",
        ),
    ),
    (
        "CREDIT_RATING",
        (
            "kredi derecelend",
            "kredi notu",
            "credit rating",
        ),
    ),
    (
        "LEGAL_REGULATORY",
        (
            "dava",
            "mahkeme",
            "rekabet kurulu",
            "spk",
            "ceza",
            "ruhsat",
            "izin",
            "lawsuit",
            "court",
            "regulatory",
        ),
    ),
    (
        "GOVERNANCE",
        (
            "genel kurul",
            "yonetim kurulu",
            "yonetici",
            "bagimsiz yonetim",
            "corporate governance",
            "board of directors",
        ),
    ),
    (
        "OPERATIONAL",
        (
            "uretime ara",
            "uretim dur",
            "faaliyet dur",
            "operasyon",
            "production halt",
            "operations",
        ),
    ),
)


def _fold(value: object) -> str:
    text = str(value or "").replace("ı", "i").replace("İ", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _value(row: Mapping[str, Any], *names: str) -> Any:
    normalized = {str(key).casefold(): value for key, value in row.items()}
    for name in names:
        if name.casefold() in normalized:
            return normalized[name.casefold()]
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=ISTANBUL)
    to_python = getattr(value, "to_pydatetime", None)
    if callable(to_python):
        parsed = to_python()
        if isinstance(parsed, datetime):
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=ISTANBUL)
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "nat", "none"}:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=ISTANBUL)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=ISTANBUL)
    except ValueError:
        return None


def _disclosure_id(row: Mapping[str, Any], url: str | None) -> int | None:
    explicit = _value(row, "disclosure_id", "disclosureid", "id")
    if explicit is not None:
        try:
            return int(explicit)
        except (TypeError, ValueError):
            pass
    match = re.search(r"/Bildirim/(\d+)", str(url or ""), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def classify_corporate_event(title: str, *, text: str | None = None) -> tuple[str, str]:
    folded = _fold(" ".join(part for part in (title, text) if part))
    for category, patterns in _CATEGORY_PATTERNS:
        if any(pattern in folded for pattern in patterns):
            return category, _CATEGORY_LABELS[category]
    return "OTHER", _CATEGORY_LABELS["OTHER"]


def corporate_event_from_mapping(
    row: Mapping[str, Any],
    *,
    source: str = "KAP",
) -> CorporateEvent | None:
    title = str(_value(row, "title", "headline", "subject", "baslik") or "").strip()
    if not title:
        return None
    url_value = _value(row, "url", "link")
    url = str(url_value).strip() if url_value is not None else None
    published_at = _parse_datetime(
        _value(row, "published_at", "date", "datetime", "timestamp", "publication_date")
    )
    text_value = _value(row, "summary", "description", "content", "text")
    category, category_label = classify_corporate_event(
        title,
        text=str(text_value) if text_value is not None else None,
    )
    return CorporateEvent(
        disclosure_id=_disclosure_id(row, url),
        published_at=published_at,
        title=title,
        category=category,
        category_label=category_label,
        direction="NOT_INFERRED",
        materiality="UNASSESSED",
        url=url,
        source=source,
        quality={
            "title_available": True,
            "published_at_available": published_at is not None,
            "classification_basis": "TITLE_AND_OPTIONAL_SUMMARY_KEYWORDS",
            "direction_inferred_from_category": False,
            "materiality_inferred_from_category": False,
            "content_review_required_for_direction": True,
        },
    )


def build_corporate_event_timeline(
    rows: Iterable[Mapping[str, Any]],
    *,
    source: str = "KAP",
    limit: int | None = 30,
) -> dict[str, Any]:
    events = [
        event
        for row in rows
        if (event := corporate_event_from_mapping(row, source=source)) is not None
    ]
    events.sort(
        key=lambda item: item.published_at or datetime.min.replace(tzinfo=ISTANBUL),
        reverse=True,
    )
    if limit is not None:
        events = events[: max(0, int(limit))]
    counts = Counter(event.category for event in events)
    return {
        "available": bool(events),
        "source": source,
        "event_count": len(events),
        "category_counts": dict(sorted(counts.items())),
        "events": [asdict(event) for event in events],
        "interpretation_contract": {
            "event_type_is_not_sentiment": True,
            "direction_is_not_inferred_from_category": True,
            "materiality_requires_event_specific_evidence": True,
            "no_automatic_buy_sell": True,
        },
    }


__all__ = [
    "CorporateEvent",
    "build_corporate_event_timeline",
    "classify_corporate_event",
    "corporate_event_from_mapping",
]
