from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from .fundamental_models import FinancialSnapshot, StatementType


CUMULATIVE_YTD = "CUMULATIVE_YTD"
PRICE_LEVEL_DATE = "price_level_date"


@dataclass(frozen=True)
class TTMResult:
    symbol: str
    as_of: datetime
    period_end: datetime | None
    currency: str | None
    available: bool
    method: str | None = None
    income_statement: dict[str, float | None] = field(default_factory=dict)
    cash_flow: dict[str, float | None] = field(default_factory=dict)
    components: tuple[dict[str, Any], ...] = ()
    missing_items: tuple[str, ...] = ()
    reason: str | None = None
    quality: dict[str, Any] = field(default_factory=dict)


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _normalized_block(snapshot: FinancialSnapshot, name: str) -> dict[str, float | None]:
    source = getattr(snapshot, name)
    result: dict[str, float | None] = {}
    for key, raw in source.items():
        value = _finite(raw)
        result[str(key)] = value * snapshot.scale if value is not None else None
    return result


def _canonical_basis_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    cleaned = str(value).strip()
    if not cleaned:
        return None
    iso_prefix = cleaned[:10]
    try:
        return date.fromisoformat(iso_prefix).isoformat()
    except ValueError:
        return cleaned


def _price_level_date(snapshot: FinancialSnapshot) -> tuple[str | None, bool]:
    """Return canonical TMS29 purchasing-power date and metadata conflict flag."""
    primary = _canonical_basis_date(snapshot.metadata.get(PRICE_LEVEL_DATE))
    legacy = _canonical_basis_date(snapshot.metadata.get("restatement_basis_date"))
    if primary is not None and legacy is not None and primary != legacy:
        return None, True
    return primary or legacy, False


def _inflation_accounting_active(snapshot: FinancialSnapshot) -> bool:
    value = str(snapshot.inflation_accounting or "").strip().upper()
    if not value or value in {"NONE", "NO", "FALSE", "N/A", "NOT_APPLICABLE"}:
        return False
    if value.startswith("NO_") or value.startswith("NO "):
        return False
    return any(token in value for token in ("TMS29", "IAS29", "INFLATION", "ENFLASYON"))


def _component(snapshot: FinancialSnapshot, role: str) -> dict[str, Any]:
    price_level_date, conflict = _price_level_date(snapshot)
    return {
        "role": role,
        "period_end": snapshot.period_end,
        "published_at": snapshot.published_at,
        "statement_type": snapshot.statement_type.value,
        "restatement_id": snapshot.restatement_id,
        "source": snapshot.source,
        "scale": snapshot.scale,
        "price_level_date": price_level_date,
        "price_level_date_conflict": conflict,
    }


def _latest_versions(
    snapshots: Iterable[FinancialSnapshot],
    *,
    symbol: str,
    as_of: datetime,
) -> dict[datetime, FinancialSnapshot]:
    normalized_symbol = symbol.strip().upper()
    versions: dict[datetime, FinancialSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.symbol.strip().upper() != normalized_symbol:
            continue
        if snapshot.published_at > as_of:
            continue
        current = versions.get(snapshot.period_end)
        if current is None or snapshot.published_at > current.published_at:
            versions[snapshot.period_end] = snapshot
    return versions


def _basis_value(snapshot: FinancialSnapshot, key: str) -> str | None:
    value = snapshot.metadata.get(key)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _compatibility_reason(snapshots: list[FinancialSnapshot]) -> str | None:
    if not snapshots:
        return "TTM bileşeni bulunamadı."
    currencies = {item.currency.strip().upper() for item in snapshots}
    if len(currencies) != 1:
        return "TTM bileşenlerinin para birimleri uyumlu değil."

    inflation = {str(item.inflation_accounting or "").strip().upper() for item in snapshots}
    if len(inflation) != 1:
        return "TTM bileşenlerinin enflasyon muhasebesi bazları uyumlu değil."

    for key in ("accounting_basis_id", "reporting_standard", "measurement_basis"):
        values = {_basis_value(item, key) for item in snapshots}
        known = {value for value in values if value is not None}
        if len(known) > 1:
            return f"TTM bileşenlerinin {key} metadata'sı uyumlu değil."
        if known and None in values:
            return f"TTM bileşenlerinden bazılarında {key} metadata'sı eksik."

    if any(_inflation_accounting_active(item) for item in snapshots):
        price_level_dates: list[str] = []
        for item in snapshots:
            price_level_date, conflict = _price_level_date(item)
            if conflict:
                return (
                    "TMS29 TTM bileşeninde price_level_date ile restatement_basis_date "
                    "birbiriyle çelişiyor."
                )
            if price_level_date is None:
                return (
                    "TMS29 ara dönem TTM için tüm bileşenlerde ortak satın alma gücü "
                    "bazını gösteren price_level_date metadata'sı zorunludur."
                )
            price_level_dates.append(price_level_date)
        if len(set(price_level_dates)) != 1:
            return (
                "TMS29 TTM bileşenlerinin satın alma gücü/restatement baz tarihleri "
                "uyumlu değil."
            )
    return None


def _shift_one_year_back(value: datetime) -> datetime:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        # 29 Şubat gibi tarihlerde karşılaştırılabilir önceki yıl son günü.
        return value.replace(year=value.year - 1, day=28)


def _combine_ytd(
    annual: dict[str, float | None],
    current_ytd: dict[str, float | None],
    prior_ytd: dict[str, float | None],
    *,
    block_name: str,
) -> tuple[dict[str, float | None], list[str]]:
    keys = sorted(set(annual) | set(current_ytd) | set(prior_ytd))
    result: dict[str, float | None] = {}
    missing: list[str] = []
    for key in keys:
        a = annual.get(key)
        c = current_ytd.get(key)
        p = prior_ytd.get(key)
        if a is None or c is None or p is None:
            result[key] = None
            missing.append(f"{block_name}.{key}")
            continue
        result[key] = a + c - p
    return result, missing


def assemble_ttm(
    snapshots: Iterable[FinancialSnapshot],
    *,
    symbol: str,
    as_of: datetime,
    current_period_end: datetime | None = None,
) -> TTMResult:
    """Point-in-time finansallardan TTM akışlarını fail-closed biçimde kurar.

    Desteklenen yöntemler:
    - Yıllık tablo için doğrudan yıllık akışlar.
    - Kümülatif ara dönem için ``önceki yıllık + cari YTD - geçen yıl aynı YTD``.

    Ara dönemlerde ``metadata['flow_basis'] == 'CUMULATIVE_YTD'`` açıkça
    belirtilmek zorundadır. Motor Türkiye'deki kümülatif raporlama alışkanlığını
    varsaymaz; provider adapter bu semantiği canonical snapshot'a yazmalıdır.

    TMS29/IAS29 uygulanan ara dönem köprülerinde üç bileşenin de aynı satın alma
    gücü bazında olduğu ayrıca kanıtlanmalıdır. ``price_level_date`` olmadan veya
    tarihler farklıyken nominal toplama/çıkarma yapılmaz.
    """
    if as_of.tzinfo is None:
        raise ValueError("as_of timezone-aware olmalıdır.")
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol boş olamaz.")

    versions = _latest_versions(snapshots, symbol=normalized_symbol, as_of=as_of)
    if not versions:
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=None,
            currency=None,
            available=False,
            reason="As-of zamanı itibarıyla kullanılabilir finansal snapshot yok.",
        )

    if current_period_end is not None:
        current = versions.get(current_period_end)
        if current is None:
            return TTMResult(
                symbol=normalized_symbol,
                as_of=as_of,
                period_end=current_period_end,
                currency=None,
                available=False,
                reason="İstenen dönem için as-of zamanı itibarıyla yayımlanmış snapshot yok.",
            )
    else:
        current = max(versions.values(), key=lambda item: item.period_end)

    if current.statement_type == StatementType.ANNUAL:
        price_level_date, _ = _price_level_date(current)
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=current.period_end,
            currency=current.currency,
            available=True,
            method="ANNUAL_DIRECT",
            income_statement=_normalized_block(current, "income_statement"),
            cash_flow=_normalized_block(current, "cash_flow"),
            components=(_component(current, "CURRENT_ANNUAL"),),
            quality={
                "point_in_time": True,
                "normalized_scale": 1.0,
                "flow_basis": "ANNUAL",
                "price_level_date": price_level_date,
            },
        )

    flow_basis = str(current.metadata.get("flow_basis") or "").strip().upper()
    if flow_basis != CUMULATIVE_YTD:
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=current.period_end,
            currency=current.currency,
            available=False,
            reason=(
                "Ara dönem TTM için flow_basis=CUMULATIVE_YTD açıkça belirtilmemiş; "
                "çeyrek/kümülatif semantiği tahmin edilmiyor."
            ),
        )

    prior_ytd_end = _shift_one_year_back(current.period_end)
    prior_ytd = versions.get(prior_ytd_end)
    annual_candidates = [
        item
        for item in versions.values()
        if item.statement_type == StatementType.ANNUAL
        and prior_ytd_end < item.period_end < current.period_end
    ]
    prior_annual = max(annual_candidates, key=lambda item: item.period_end, default=None)

    if prior_ytd is None or prior_annual is None:
        missing = []
        if prior_annual is None:
            missing.append("önceki yıllık tablo")
        if prior_ytd is None:
            missing.append("geçen yıl aynı ara dönem")
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=current.period_end,
            currency=current.currency,
            available=False,
            reason="TTM bileşenleri eksik: " + ", ".join(missing) + ".",
        )

    prior_flow_basis = str(prior_ytd.metadata.get("flow_basis") or "").strip().upper()
    if prior_flow_basis != CUMULATIVE_YTD:
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=current.period_end,
            currency=current.currency,
            available=False,
            reason="Geçen yıl aynı ara dönem CUMULATIVE_YTD olarak işaretli değil.",
        )

    components = [prior_annual, current, prior_ytd]
    incompatible = _compatibility_reason(components)
    if incompatible:
        return TTMResult(
            symbol=normalized_symbol,
            as_of=as_of,
            period_end=current.period_end,
            currency=current.currency,
            available=False,
            reason=incompatible,
        )

    annual_income = _normalized_block(prior_annual, "income_statement")
    current_income = _normalized_block(current, "income_statement")
    prior_income = _normalized_block(prior_ytd, "income_statement")
    annual_cash = _normalized_block(prior_annual, "cash_flow")
    current_cash = _normalized_block(current, "cash_flow")
    prior_cash = _normalized_block(prior_ytd, "cash_flow")

    income, missing_income = _combine_ytd(
        annual_income,
        current_income,
        prior_income,
        block_name="income_statement",
    )
    cash, missing_cash = _combine_ytd(
        annual_cash,
        current_cash,
        prior_cash,
        block_name="cash_flow",
    )
    price_level_date, _ = _price_level_date(current)

    return TTMResult(
        symbol=normalized_symbol,
        as_of=as_of,
        period_end=current.period_end,
        currency=current.currency,
        available=True,
        method="ANNUAL_PLUS_CURRENT_YTD_MINUS_PRIOR_YTD",
        income_statement=income,
        cash_flow=cash,
        components=(
            _component(prior_annual, "PRIOR_ANNUAL"),
            _component(current, "CURRENT_YTD"),
            _component(prior_ytd, "PRIOR_YTD"),
        ),
        missing_items=tuple(missing_income + missing_cash),
        quality={
            "point_in_time": True,
            "normalized_scale": 1.0,
            "flow_basis": CUMULATIVE_YTD,
            "partial_line_items_allowed": True,
            "price_level_date": price_level_date,
        },
    )
