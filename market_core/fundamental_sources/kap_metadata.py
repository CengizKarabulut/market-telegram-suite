from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


ISTANBUL = ZoneInfo("Europe/Istanbul")


@dataclass(frozen=True)
class KapFilingMetadata:
    disclosure_id: int | None
    title: str | None
    published_at: datetime | None
    disclosure_type: str | None
    report_year: int | None
    period_label: str | None
    period_end: datetime | None
    currency: str | None
    consolidation: str | None
    url: str | None
    quality: dict[str, object]


def _visible_text(raw_html: str) -> str:
    text = html_lib.unescape(raw_html or "")
    # Next.js payloads often contain escaped unicode/tag delimiters.
    text = text.replace("\\u003c", "<").replace("\\u003e", ">")
    text = text.replace("\\n", " ").replace("\\t", " ")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace('\\"', '"')
    return re.sub(r"\s+", " ", text).strip()


def _first(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" :-|")
            if value:
                return value
    return None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=ISTANBUL)
        except ValueError:
            pass
    return None


def _parse_period_end(text: str, year: int | None, period_label: str | None) -> tuple[datetime | None, str | None]:
    # Prefer the exact KAP Current Period date; this also works for non-calendar fiscal years.
    exact = _first(
        (
            r"Cari Dönem\s+(\d{2}\.\d{2}\.\d{4})\s+Current Period",
            r"Current Period\s+(\d{2}\.\d{2}\.\d{4})",
            r"Finansal Raporlar?\s*[-–]\s*(\d{1,2}\s+[A-Za-zÇĞİÖŞÜçğıöşü]+\s+\d{4})",
        ),
        text,
    )
    if exact:
        for fmt in ("%d.%m.%Y", "%d %B %Y"):
            try:
                # Turkish month names are not locale-safe; numeric KAP date is preferred.
                if fmt == "%d %B %Y":
                    break
                parsed = datetime.strptime(exact, fmt).replace(tzinfo=ISTANBUL)
                return parsed, "KAP_CURRENT_PERIOD"
            except ValueError:
                pass

    if year is None or not period_label:
        return None, None
    normalized = period_label.casefold()
    month_day = None
    if "3 ayl" in normalized:
        month_day = (3, 31)
    elif "6 ayl" in normalized:
        month_day = (6, 30)
    elif "9 ayl" in normalized:
        month_day = (9, 30)
    elif "12 ayl" in normalized or "yıll" in normalized:
        month_day = (12, 31)
    if month_day is None:
        return None, None
    month, day = month_day
    return datetime(year, month, day, tzinfo=ISTANBUL), "YEAR_PERIOD_FALLBACK"


def _normalize_currency(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().upper()
    if cleaned in {"TL", "TRY", "TÜRK LİRASI", "TURKISH LIRA"}:
        return "TRY"
    return cleaned


def parse_kap_financial_report_html(
    raw_html: str,
    *,
    disclosure_id: int | None = None,
    title: str | None = None,
    url: str | None = None,
) -> KapFilingMetadata:
    """Parse exact publication/period metadata from a KAP financial filing page.

    The adapter intentionally does not infer publication time from the financial
    period. ``published_at`` only comes from KAP's displayed submission time.
    ``period_end`` prefers the filing's exact Current Period date and only falls
    back to year/period labels when that date is absent.
    """
    text = _visible_text(raw_html)

    published_raw = _first(
        (
            r"Gönderim Tarihi\s+(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})",
            r"Gönderim Tarihi\s+(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})",
            r"KAP'ta yayınlanma tarihi ve saati\s*:?\s*(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})",
        ),
        text,
    )
    published_at = _parse_timestamp(published_raw)

    disclosure_type = _first(
        (
            r"Bildirim Tipi\s+([A-Z]{2,4})\b",
            r'disclosureType(?:Code)?["\\: ]+([A-Z]{2,4})\b',
        ),
        text,
    )
    year_raw = _first((r"\bYıl\s+(\d{4})\b", r'year["\\: ]+(\d{4})\b'), text)
    try:
        report_year = int(year_raw) if year_raw else None
    except ValueError:
        report_year = None

    period_label = _first(
        (
            r"Periyot\s+([^|]{2,24}?)(?=\s+(?:Bildirim Ekleri|Finansal Rapor|Özet Bilgi|Sunum Para Birimi))",
            r'period(?:Name)?["\\: ]+([^"\\]{2,24})',
        ),
        text,
    )
    if period_label:
        period_label = period_label.strip()

    currency = _normalize_currency(
        _first(
            (
                r"Sunum Para Birimi\s+([A-ZÇĞİÖŞÜa-zçğıöşü ]{2,24}?)(?=\s+(?:Finansal Tablo Niteliği|Dipnot|Cari Dönem))",
                r"Presentation Currency\s+([A-Z]{3})\b",
            ),
            text,
        )
    )
    consolidation = _first(
        (
            r"Finansal Tablo Niteliği\s+(.+?)(?=\s+(?:İlgili Şirketler|Dipnot Referansı|Cari Dönem|İngilizce|Türkçe))",
        ),
        text,
    )

    period_end, period_end_source = _parse_period_end(text, report_year, period_label)
    if url is None and disclosure_id is not None:
        url = f"https://www.kap.org.tr/tr/Bildirim/{disclosure_id}"

    missing = [
        name
        for name, value in (
            ("published_at", published_at),
            ("report_year", report_year),
            ("period_label", period_label),
            ("period_end", period_end),
        )
        if value is None
    ]
    return KapFilingMetadata(
        disclosure_id=disclosure_id,
        title=title,
        published_at=published_at,
        disclosure_type=disclosure_type,
        report_year=report_year,
        period_label=period_label,
        period_end=period_end,
        currency=currency,
        consolidation=consolidation,
        url=url,
        quality={
            "source": "KAP",
            "exact_publication_timestamp": published_at is not None,
            "period_end_source": period_end_source,
            "missing": missing,
        },
    )
