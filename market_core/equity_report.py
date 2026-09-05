from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .serialization import to_primitive


EQUITY_REPORT_SCHEMA = "v4-equity-report/1"

_BULLISH_TECHNICAL = {
    "BULLISH_ALIGNMENT",
    "EARLY_RECOVERY",
    "BULLISH_STRUCTURE_WITH_PULLBACK",
}
_BEARISH_TECHNICAL = {"BEARISH_ALIGNMENT"}
_POSITIVE_FUNDAMENTAL = {"CURRENT_PERIOD_POSITIVE"}
_RISK_FUNDAMENTAL = {"QUALITY_RISKS_DOMINATE"}
_MIXED_FUNDAMENTAL = {"MIXED_BALANCE_STRONGER_THAN_EARNINGS_QUALITY"}
_POSITIVE_PEER = {"RELATIVELY_FAVOURABLE"}
_NEGATIVE_PEER = {"RELATIVELY_UNFAVOURABLE"}


def _dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None:
        return {}
    primitive = to_primitive(value)
    return dict(primitive) if isinstance(primitive, Mapping) else {}


def _state(block: Mapping[str, Any], *path: str) -> str | None:
    current: Any = block
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    text = str(current or "").strip().upper()
    return text or None


def _peer_highlights(peer: Mapping[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    rows: list[tuple[int, str, Mapping[str, Any]]] = []
    priority = {"FAVOURABLE": 0, "UNFAVOURABLE": 1, "CONTEXTUAL": 2, "NEUTRAL": 3}
    for name, raw in (peer.get("metrics") or {}).items():
        if not isinstance(raw, Mapping) or not raw.get("available"):
            continue
        rows.append((priority.get(str(raw.get("favourability")), 9), str(name), raw))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [
        {
            "metric": name,
            "target_value": raw.get("target_value"),
            "peer_median": raw.get("peer_median"),
            "peer_mean": raw.get("peer_mean"),
            "peer_q1": raw.get("peer_q1"),
            "peer_q3": raw.get("peer_q3"),
            "percentile_rank": raw.get("percentile_rank"),
            "position": raw.get("position"),
            "favourability": raw.get("favourability"),
            "scope": raw.get("scope"),
            "benchmark_group": raw.get("benchmark_group"),
            "basis": raw.get("basis"),
            "comment": raw.get("comment"),
        }
        for _, name, raw in rows[:limit]
    ]


def _integrated_synthesis(
    *,
    technical: Mapping[str, Any],
    fundamental: Mapping[str, Any],
    peer: Mapping[str, Any],
    valuation: Mapping[str, Any],
) -> dict[str, Any]:
    tech_state = _state(technical, "technical_synthesis", "state")
    if tech_state is None:
        tech_state = _state(technical, "technical_synthesis", "technical_state")
    fundamental_state = _state(fundamental, "synthesis", "state")
    peer_state = _state(peer, "synthesis", "state")

    positives: list[str] = []
    risks: list[str] = []
    conflicts: list[str] = []
    context: list[str] = []

    if tech_state in _BULLISH_TECHNICAL:
        positives.append("Teknik eksende toparlanma/olumlu hizalanma işaretleri var.")
    elif tech_state in _BEARISH_TECHNICAL:
        risks.append("Teknik eksende aşağı yönlü hizalanma baskın.")
    elif tech_state:
        context.append("Teknik görünüm tek yönlü değil; yapı ve momentum birlikte izlenmeli.")

    if fundamental_state in _POSITIVE_FUNDAMENTAL:
        positives.append("Cari temel görünümde bilanço ve faaliyet göstergeleri olumlu unsurlar taşıyor.")
    elif fundamental_state in _RISK_FUNDAMENTAL:
        risks.append("Cari finansallarda kâr kalitesi/nakit dönüşümü riskleri baskın.")
    elif fundamental_state in _MIXED_FUNDAMENTAL:
        positives.append("Bilanço tarafında görece güçlü unsurlar var.")
        risks.append("Kârın nakit dönüşümü veya gelir bileşimi bilanço kadar güçlü değil.")

    if peer_state in _POSITIVE_PEER:
        positives.append("Karşılaştırılabilir metriklerde şirket eş grubuna/sektöre göre olumlu ayrışıyor.")
    elif peer_state in _NEGATIVE_PEER:
        risks.append("Karşılaştırılabilir metriklerde şirket eş grubuna/sektöre göre zayıf ayrışıyor.")
    elif peer_state:
        context.append("Sektör/eş şirket karşılaştırması tek yönlü üstünlük göstermiyor.")

    if tech_state in _BEARISH_TECHNICAL and fundamental_state in _POSITIVE_FUNDAMENTAL:
        conflicts.append(
            "Temel görünüm olumlu olsa da teknik yapı bunu henüz teyit etmiyor; iki eksen farklı yönde."
        )
    if tech_state in _BULLISH_TECHNICAL and fundamental_state in _RISK_FUNDAMENTAL:
        conflicts.append(
            "Teknik toparlanma temel kalite riskleriyle çelişiyor; fiyat momentumu tek başına yeterli teyit değil."
        )
    if tech_state in _BEARISH_TECHNICAL and peer_state in _POSITIVE_PEER:
        conflicts.append(
            "Sektöre göre güçlü metrikler mevcut teknik zayıflığı tek başına ortadan kaldırmıyor."
        )
    if tech_state in _BULLISH_TECHNICAL and peer_state in _NEGATIVE_PEER:
        conflicts.append(
            "Teknik görünüm olumlu olsa da şirket temel/çarpan metriklerinde eş grubuna göre zayıf ayrışıyor."
        )

    if valuation.get("available"):
        context.append(
            "Değerleme çarpanları bağlamsal okunur; sektör medyanına göre düşük/yüksek olmak otomatik ucuz/pahalı kararı değildir."
        )

    if conflicts:
        state = "CROSS_AXIS_CONFLICT"
        headline = "Teknik, temel ve sektör eksenleri aynı yönde değil; karar kalitesi için teyit gerekiyor."
    elif positives and risks:
        state = "MIXED"
        headline = "Şirkette olumlu ve zayıf unsurlar birlikte bulunuyor; tek eksenli yorum yeterli değil."
    elif positives and not risks:
        state = "MULTI_AXIS_POSITIVE"
        headline = "Mevcut veriler teknik/temel/sektör eksenlerinde ağırlıklı olarak olumlu bir tablo gösteriyor."
    elif risks and not positives:
        state = "MULTI_AXIS_RISK"
        headline = "Mevcut veriler teknik/temel/sektör eksenlerinde risklerin daha ağır bastığını gösteriyor."
    else:
        state = "INSUFFICIENT_OR_NEUTRAL"
        headline = "Bütünleşik yorum için yeterli veya tek yönlü kanıt oluşmamış durumda."

    return {
        "state": state,
        "headline": headline,
        "technical_state": tech_state,
        "fundamental_state": fundamental_state,
        "peer_state": peer_state,
        "positives": positives,
        "risks": risks,
        "conflicts": conflicts,
        "context": context,
        "decision_contract": {
            "auto_buy_sell": False,
            "single_score": False,
            "axes_kept_separate": True,
        },
    }


def build_equity_report_contract(
    *,
    symbol: str,
    technical_report: Mapping[str, Any] | None = None,
    current_fundamental_view: Mapping[str, Any] | None = None,
    fundamental_state: Mapping[str, Any] | None = None,
    valuation_state: Any = None,
    peer_benchmark: Mapping[str, Any] | None = None,
    corporate_events: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compose the V4 full-equity contract without changing production /rapor.

    Each analytical axis remains independently inspectable. The integrated
    synthesis may describe agreement/conflict, but it never collapses technical,
    fundamental, peer and valuation evidence into a single opaque score.
    """
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol boş olamaz")

    technical = _dict(technical_report)
    current_fundamental = _dict(current_fundamental_view)
    fundamentals = _dict(fundamental_state)
    valuation = _dict(valuation_state)
    peer = _dict(peer_benchmark)
    events = [dict(item) for item in (corporate_events or [])]

    fundamental_for_synthesis = current_fundamental or fundamentals
    integrated = _integrated_synthesis(
        technical=technical,
        fundamental=fundamental_for_synthesis,
        peer=peer,
        valuation=valuation,
    )

    report = {
        "schema": EQUITY_REPORT_SCHEMA,
        "symbol": normalized_symbol,
        "availability": {
            "technical": bool(technical),
            "current_fundamental": bool(current_fundamental.get("available")),
            "ttm_fundamental": bool(fundamentals.get("available")),
            "valuation": bool(valuation.get("available")),
            "peer_benchmark": bool(peer.get("available")),
            "corporate_events": bool(events),
        },
        "technical": technical,
        "fundamental": {
            "current_period": current_fundamental,
            "ttm": fundamentals,
        },
        "sector_and_peers": {
            "benchmark": peer,
            "highlights": _peer_highlights(peer),
        },
        "valuation": valuation,
        "corporate_events": events,
        "integrated_synthesis": integrated,
        "data_contract": {
            "no_single_score": True,
            "no_automatic_buy_sell": True,
            "point_in_time_required_for_historical_fundamentals": True,
            "peer_metric_basis_must_match": True,
            "sector_mean_is_secondary_to_median_and_quartiles": True,
        },
    }
    return to_primitive(report)


def format_equity_report_preview(report: Mapping[str, Any]) -> str:
    symbol = str(report.get("symbol") or "—")
    synthesis = report.get("integrated_synthesis") or {}
    lines = [
        f"{symbol} — V4 Bütünleşik Hisse Analizi",
        str(synthesis.get("headline") or "Bütünleşik analiz özeti üretilemedi."),
    ]

    positives = list(synthesis.get("positives") or [])
    risks = list(synthesis.get("risks") or [])
    conflicts = list(synthesis.get("conflicts") or [])
    if positives:
        lines.extend(["", "Olumlu taraflar:", *[f"• {item}" for item in positives[:4]]])
    if risks:
        lines.extend(["", "Riskler:", *[f"• {item}" for item in risks[:4]]])
    if conflicts:
        lines.extend(["", "Çelişkiler / teyit gerekenler:", *[f"• {item}" for item in conflicts[:4]]])

    highlights = (report.get("sector_and_peers") or {}).get("highlights") or []
    if highlights:
        lines.extend(["", "Sektör / eş şirket konumu:"])
        for item in highlights[:5]:
            scope = (
                "eş grup"
                if item.get("scope") == "INDUSTRY_PEER_GROUP"
                else "geniş sektör"
            )
            lines.append(
                f"• {item.get('metric')}: {item.get('position')} · "
                f"{item.get('favourability')} · {scope}"
            )

    lines.extend(
        [
            "",
            "Not: Teknik, temel, değerleme ve sektör karşılaştırması ayrı kanıt eksenleridir; otomatik AL/SAT veya tek puan üretilmez.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "EQUITY_REPORT_SCHEMA",
    "build_equity_report_contract",
    "format_equity_report_preview",
]
