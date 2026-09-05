from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from statistics import mean, median
from typing import Any

from .fundamental_models import SectorType
from .sector_profiles import SectorMetricRule, profile_for_sector


@dataclass(frozen=True)
class PeerObservation:
    symbol: str
    peer_group: str
    sector_type: SectorType
    metrics: Mapping[str, float | None]
    metric_basis: Mapping[str, str] = field(default_factory=dict)
    as_of: datetime | None = None
    period_end: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("PeerObservation symbol boş olamaz.")
        if not self.peer_group.strip():
            raise ValueError("PeerObservation peer_group boş olamaz.")


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _quantile(values: list[float], q: float) -> float:
    if not values:
        raise ValueError("values boş olamaz")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _percentile_rank(value: float, peers: list[float]) -> float:
    if not peers:
        return 0.5
    less = sum(item < value for item in peers)
    equal = sum(item == value for item in peers)
    return (less + 0.5 * equal) / len(peers)


def _position(value: float, *, q1: float, med: float, q3: float) -> str:
    if value >= q3:
        return "TOP_QUARTILE"
    if value > med:
        return "ABOVE_MEDIAN"
    if value == med:
        return "AT_MEDIAN"
    if value > q1:
        return "BELOW_MEDIAN"
    return "BOTTOM_QUARTILE"


def _favourability(position: str, rule: SectorMetricRule) -> str:
    if rule.direction == "CONTEXTUAL":
        return "CONTEXTUAL"
    high_side = position in {"TOP_QUARTILE", "ABOVE_MEDIAN"}
    low_side = position in {"BOTTOM_QUARTILE", "BELOW_MEDIAN"}
    if position == "AT_MEDIAN":
        return "NEUTRAL"
    if rule.direction == "HIGHER_BETTER":
        return "FAVOURABLE" if high_side else "UNFAVOURABLE" if low_side else "NEUTRAL"
    return "FAVOURABLE" if low_side else "UNFAVOURABLE" if high_side else "NEUTRAL"


def _comment(label: str, position: str, favourability: str) -> str:
    where = {
        "TOP_QUARTILE": "karşılaştırma grubunun üst çeyreğinde",
        "ABOVE_MEDIAN": "karşılaştırma grubu medyanının üzerinde",
        "AT_MEDIAN": "karşılaştırma grubu medyanı civarında",
        "BELOW_MEDIAN": "karşılaştırma grubu medyanının altında",
        "BOTTOM_QUARTILE": "karşılaştırma grubunun alt çeyreğinde",
    }.get(position, "karşılaştırma dağılımı içinde")
    suffix = {
        "FAVOURABLE": "; bu metrikte göreli görünüm olumlu.",
        "UNFAVOURABLE": "; bu metrikte göreli görünüm zayıf.",
        "NEUTRAL": ".",
        "CONTEXTUAL": "; tek başına iyi/kötü yorumu yapılmamalı.",
    }.get(favourability, ".")
    return f"{label} {where}{suffix}"


def _benchmark_one_metric(
    *,
    target_value: float | None,
    peer_values: list[float],
    rule: SectorMetricRule,
    basis: str | None,
    basis_excluded_count: int,
) -> dict[str, Any]:
    if target_value is None:
        return {
            "available": False,
            "reason": "Hedef şirket metriği mevcut değil.",
            "peer_count": len(peer_values),
            "basis": basis,
        }
    if len(peer_values) < rule.minimum_peers:
        return {
            "available": False,
            "reason": (
                f"Sağlıklı karşılaştırma için en az {rule.minimum_peers} eş şirket gerekli; "
                f"uyumlu bazda {len(peer_values)} bulundu."
            ),
            "peer_count": len(peer_values),
            "basis_excluded_count": basis_excluded_count,
            "target_value": target_value,
            "basis": basis,
        }

    q1 = _quantile(peer_values, 0.25)
    med = median(peer_values)
    avg = mean(peer_values)
    q3 = _quantile(peer_values, 0.75)
    position = _position(target_value, q1=q1, med=med, q3=q3)
    favourability = _favourability(position, rule)

    return {
        "available": True,
        "target_value": target_value,
        "peer_count": len(peer_values),
        "basis_excluded_count": basis_excluded_count,
        "basis": basis,
        "peer_mean": avg,
        "peer_median": med,
        "peer_q1": q1,
        "peer_q3": q3,
        "peer_min": min(peer_values),
        "peer_max": max(peer_values),
        "delta_to_median": target_value - med,
        "delta_to_mean": target_value - avg,
        "percentile_rank": _percentile_rank(target_value, peer_values),
        "position": position,
        "direction": rule.direction,
        "favourability": favourability,
        "comment": _comment(rule.label, position, favourability),
    }


def _synthesis(metric_results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    favourable = [
        name
        for name, result in metric_results.items()
        if result.get("available") and result.get("favourability") == "FAVOURABLE"
    ]
    unfavourable = [
        name
        for name, result in metric_results.items()
        if result.get("available") and result.get("favourability") == "UNFAVOURABLE"
    ]
    contextual = [
        name
        for name, result in metric_results.items()
        if result.get("available") and result.get("favourability") == "CONTEXTUAL"
    ]
    available_count = sum(bool(result.get("available")) for result in metric_results.values())

    if available_count == 0:
        state = "INSUFFICIENT_PEER_DATA"
        headline = "Sektör/eş şirket karşılaştırması için yeterli ortak metrik yok."
    elif favourable and unfavourable:
        state = "MIXED"
        headline = "Şirket karşılaştırma grubuna göre bazı metriklerde güçlü, bazılarında zayıf ayrışıyor."
    elif favourable and not unfavourable:
        state = "RELATIVELY_FAVOURABLE"
        headline = "Mevcut karşılaştırılabilir metriklerde şirket grubuna göre olumlu ayrışıyor."
    elif unfavourable and not favourable:
        state = "RELATIVELY_UNFAVOURABLE"
        headline = "Mevcut karşılaştırılabilir metriklerde şirket grubuna göre zayıf ayrışıyor."
    else:
        state = "NEUTRAL_OR_CONTEXTUAL"
        headline = "Karşılaştırma belirgin tek yönlü üstünlük veya zayıflık göstermiyor."

    return {
        "state": state,
        "headline": headline,
        "favourable_metrics": favourable,
        "unfavourable_metrics": unfavourable,
        "contextual_metrics": contextual,
    }


def build_peer_benchmark(
    *,
    target_symbol: str,
    peer_group: str,
    sector_type: SectorType,
    observations: Iterable[PeerObservation],
    target_metrics: Mapping[str, float | None] | None = None,
    target_metric_basis: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Compare a company with same-group peers using robust distribution stats.

    The target company is excluded from peer statistics. Metrics are compared
    only when their declared basis matches the target (for example TTM with TTM,
    current-YTD with current-YTD). Median and quartiles are the primary anchors;
    mean is exposed only as a secondary reference because BIST ratios can carry
    strong outliers.
    """
    symbol = target_symbol.strip().upper()
    group = peer_group.strip()
    if not symbol:
        raise ValueError("target_symbol boş olamaz")
    if not group:
        raise ValueError("peer_group boş olamaz")

    rows = [
        item
        for item in observations
        if item.peer_group.strip() == group and item.sector_type == sector_type
    ]
    target_row = next((item for item in rows if item.symbol.strip().upper() == symbol), None)
    metrics = dict(
        target_metrics
        if target_metrics is not None
        else (target_row.metrics if target_row is not None else {})
    )
    bases = dict(
        target_metric_basis
        if target_metric_basis is not None
        else (target_row.metric_basis if target_row is not None else {})
    )
    peers = [item for item in rows if item.symbol.strip().upper() != symbol]
    profile = profile_for_sector(sector_type)

    metric_results: dict[str, dict[str, Any]] = {}
    for rule in profile.metric_rules:
        target_value = _finite(metrics.get(rule.metric))
        target_basis = str(bases.get(rule.metric) or "").strip() or None
        peer_values: list[float] = []
        basis_excluded_count = 0
        for item in peers:
            value = _finite(item.metrics.get(rule.metric))
            if value is None:
                continue
            peer_basis = str(item.metric_basis.get(rule.metric) or "").strip() or None
            if target_basis is not None and peer_basis != target_basis:
                basis_excluded_count += 1
                continue
            peer_values.append(value)
        metric_results[rule.metric] = _benchmark_one_metric(
            target_value=target_value,
            peer_values=peer_values,
            rule=rule,
            basis=target_basis,
            basis_excluded_count=basis_excluded_count,
        )

    synthesis = _synthesis(metric_results)
    available_count = sum(bool(result.get("available")) for result in metric_results.values())

    return {
        "available": available_count > 0,
        "symbol": symbol,
        "peer_group": group,
        "sector_type": sector_type.value,
        "profile": profile.code,
        "profile_label": profile.label,
        "peer_company_count": len(peers),
        "metrics": metric_results,
        "synthesis": synthesis,
        "quality": {
            "target_excluded_from_peer_stats": True,
            "primary_location_statistic": "MEDIAN_AND_QUARTILES",
            "mean_is_secondary_reference": True,
            "peer_group_must_be_same_business_context": True,
            "metric_basis_must_match_when_declared": True,
        },
    }


def _provider_sector_key(item: PeerObservation) -> str | None:
    text = str(item.metadata.get("sector") or "").strip()
    return text.casefold() if text else None


def build_hierarchical_peer_benchmark(
    *,
    target_symbol: str,
    peer_group: str,
    sector_type: SectorType,
    observations: Iterable[PeerObservation],
    target_metrics: Mapping[str, float | None] | None = None,
    target_metric_basis: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Use industry, provider-sector and broad-archetype peers in that order.

    Fallback is metric-by-metric and never silent. A THYAO-like company can first
    be compared with airlines, then (if the airline sample is too small) with its
    provider sector such as transportation, and only as a last resort with the
    broad INDUSTRIAL archetype. When provider-sector metadata is absent, the
    older industry -> broad-archetype behaviour is preserved.
    """
    rows = list(observations)
    symbol = target_symbol.strip().upper()
    exact = build_peer_benchmark(
        target_symbol=symbol,
        peer_group=peer_group,
        sector_type=sector_type,
        observations=rows,
        target_metrics=target_metrics,
        target_metric_basis=target_metric_basis,
    )

    target_row = next(
        (
            item
            for item in rows
            if item.symbol.strip().upper() == symbol and item.sector_type == sector_type
        ),
        None,
    )
    provider_sector_key = _provider_sector_key(target_row) if target_row is not None else None
    provider_sector_label = (
        str(target_row.metadata.get("sector") or "").strip()
        if target_row is not None and provider_sector_key
        else None
    )
    if provider_sector_key:
        provider_group = f"PROVIDER_SECTOR::{provider_sector_key}"
        provider_rows = [
            replace(item, peer_group=provider_group)
            for item in rows
            if item.sector_type == sector_type and _provider_sector_key(item) == provider_sector_key
        ]
        provider_sector = build_peer_benchmark(
            target_symbol=symbol,
            peer_group=provider_group,
            sector_type=sector_type,
            observations=provider_rows,
            target_metrics=target_metrics,
            target_metric_basis=target_metric_basis,
        )
    else:
        provider_group = None
        provider_sector = {
            "available": False,
            "reason": "Provider sektör metadata'sı yok; orta kademe karşılaştırma atlandı.",
            "metrics": {},
            "synthesis": {
                "state": "INSUFFICIENT_PEER_DATA",
                "headline": "Provider sektör karşılaştırması kullanılamıyor.",
            },
        }

    broad_group = f"BROAD_{sector_type.value}"
    broad_rows = [
        replace(item, peer_group=broad_group)
        for item in rows
        if item.sector_type == sector_type
    ]
    broad = build_peer_benchmark(
        target_symbol=symbol,
        peer_group=broad_group,
        sector_type=sector_type,
        observations=broad_rows,
        target_metrics=target_metrics,
        target_metric_basis=target_metric_basis,
    )

    effective_metrics: dict[str, dict[str, Any]] = {}
    all_names = (
        set(exact.get("metrics", {}))
        | set(provider_sector.get("metrics", {}))
        | set(broad.get("metrics", {}))
    )
    for name in sorted(all_names):
        exact_metric = dict((exact.get("metrics") or {}).get(name) or {})
        provider_metric = dict((provider_sector.get("metrics") or {}).get(name) or {})
        broad_metric = dict((broad.get("metrics") or {}).get(name) or {})
        if exact_metric.get("available"):
            exact_metric["scope"] = "INDUSTRY_PEER_GROUP"
            exact_metric["benchmark_group"] = peer_group
            effective_metrics[name] = exact_metric
        elif provider_metric.get("available"):
            provider_metric["scope"] = "PROVIDER_SECTOR_FALLBACK"
            provider_metric["benchmark_group"] = provider_group
            provider_metric["benchmark_label"] = provider_sector_label
            provider_metric["fallback_reason"] = exact_metric.get("reason")
            effective_metrics[name] = provider_metric
        elif broad_metric.get("available"):
            broad_metric["scope"] = "BROAD_SECTOR_FALLBACK"
            broad_metric["benchmark_group"] = broad_group
            broad_metric["fallback_reason"] = (
                provider_metric.get("reason") or exact_metric.get("reason")
            )
            effective_metrics[name] = broad_metric
        else:
            effective_metrics[name] = {
                **exact_metric,
                "scope": "UNAVAILABLE",
                "provider_sector_reason": provider_metric.get("reason"),
                "broad_sector_reason": broad_metric.get("reason"),
            }

    effective_synthesis = _synthesis(effective_metrics)
    available_count = sum(bool(item.get("available")) for item in effective_metrics.values())
    provider_fallback_metrics = [
        name
        for name, item in effective_metrics.items()
        if item.get("scope") == "PROVIDER_SECTOR_FALLBACK"
    ]
    broad_fallback_metrics = [
        name
        for name, item in effective_metrics.items()
        if item.get("scope") == "BROAD_SECTOR_FALLBACK"
    ]

    return {
        "available": available_count > 0,
        "symbol": symbol,
        "sector_type": sector_type.value,
        "preferred_peer_group": peer_group,
        "provider_sector": provider_sector_label,
        "industry_benchmark": exact,
        "provider_sector_benchmark": provider_sector,
        "broad_sector_benchmark": broad,
        "metrics": effective_metrics,
        "synthesis": effective_synthesis,
        "provider_sector_fallback_metrics": provider_fallback_metrics,
        "broad_sector_fallback_metrics": broad_fallback_metrics,
        "fallback_metrics": provider_fallback_metrics + broad_fallback_metrics,
        "quality": {
            "industry_first": True,
            "provider_sector_second": True,
            "broad_archetype_last": True,
            "fallback_is_explicit": True,
            "fallback_is_metric_specific": True,
            "metric_basis_must_match_when_declared": True,
        },
    }


__all__ = [
    "PeerObservation",
    "build_hierarchical_peer_benchmark",
    "build_peer_benchmark",
]
