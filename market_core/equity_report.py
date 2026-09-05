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

_METRIC_LABELS = {
    "revenue_growth": "Ciro büyümesi",
    "net_income_growth": "Net kâr büyümesi",
    "gross_margin": "Brüt kâr marjı",
    "ebitda_margin": "FAVÖK marjı",
    "net_margin": "Net kâr marjı",
    "roe": "Özkaynak kârlılığı",
    "roa": "Aktif kârlılığı",
    "roic": "Yatırılmış sermaye getirisi",
    "net_debt_to_ebitda": "Net borç/FAVÖK",
    "interest_coverage": "Faiz karşılama",
    "operating_cash_flow_to_net_income": "Nakit dönüşümü",
    "ltv": "Kredi/değer oranı (LTV)",
    "rental_revenue_share": "Kira gelirlerinin payı",
    "fair_value_gain_share_of_pretax": "Değerleme kazancının kârdaki payı",
    "price_to_nav": "Fiyat/NAD",
    "nav_discount": "NAD iskontosu",
    "net_interest_margin": "Net faiz/finansman marjı",
    "capital_adequacy_ratio": "Sermaye yeterlilik oranı",
    "npl_ratio": "Takipteki kredi/alacak oranı",
    "cost_to_income": "Maliyet/gelir oranı",
    "loan_to_deposit": "Kredi/mevduat oranı",
    "price_to_book": "Fiyat/defter değeri",
    "premium_growth": "Prim üretimi büyümesi",
    "combined_ratio": "Bileşik rasyo",
    "loss_ratio": "Hasar/prim oranı",
    "solvency_ratio": "Solvency oranı",
    "investment_income_share": "Yatırım gelirlerinin kârdaki payı",
    "holding_net_debt_to_nav": "Holding net borç/NAD",
    "cash_dividend_income_share": "Temettü gelir payı",
    "pe": "F/K",
    "ev_to_ebitda": "FD/FAVÖK",
    "price_to_sales": "Fiyat/Satışlar",
}

_PERCENT_METRICS = {
    "revenue_growth",
    "net_income_growth",
    "gross_margin",
    "ebitda_margin",
    "net_margin",
    "roe",
    "roa",
    "roic",
    "ltv",
    "rental_revenue_share",
    "fair_value_gain_share_of_pretax",
    "nav_discount",
    "operating_cash_flow_to_net_income",
    "premium_growth",
    "combined_ratio",
    "loss_ratio",
    "solvency_ratio",
    "investment_income_share",
    "capital_adequacy_ratio",
    "npl_ratio",
    "cost_to_income",
    "loan_to_deposit",
}

_MULTIPLE_METRICS = {
    "pe",
    "price_to_book",
    "ev_to_ebitda",
    "price_to_sales",
    "price_to_nav",
    "net_debt_to_ebitda",
    "holding_net_debt_to_nav",
}

_POSITION_TR = {
    "TOP_QUARTILE": "üst çeyrek",
    "ABOVE_MEDIAN": "medyanın üzerinde",
    "AT_MEDIAN": "medyan civarında",
    "BELOW_MEDIAN": "medyanın altında",
    "BOTTOM_QUARTILE": "alt çeyrek",
}

_FAVOURABILITY_TR = {
    "FAVOURABLE": "göreli olumlu",
    "UNFAVOURABLE": "göreli zayıf",
    "NEUTRAL": "nötr",
    "CONTEXTUAL": "bağlamsal",
}


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
            "metric_label": _METRIC_LABELS.get(name, name),
            "target_value": raw.get("target_value"),
            "peer_median": raw.get("peer_median"),
            "peer_mean": raw.get("peer_mean"),
            "peer_q1": raw.get("peer_q1"),
            "peer_q3": raw.get("peer_q3"),
            "delta_to_median": raw.get("delta_to_median"),
            "delta_to_mean": raw.get("delta_to_mean"),
            "percentile_rank": raw.get("percentile_rank"),
            "position": raw.get("position"),
            "favourability": raw.get("favourability"),
            "scope": raw.get("scope"),
            "benchmark_group": raw.get("benchmark_group"),
            "benchmark_label": raw.get("benchmark_label"),
            "basis": raw.get("basis"),
            "comment": raw.get("comment"),
        }
        for _, name, raw in rows[:limit]
    ]


def _corporate_context(events: list[Mapping[str, Any]]) -> list[str]:
    if not events:
        return []
    counts: dict[str, int] = {}
    for event in events:
        category = str(event.get("category") or "OTHER")
        counts[category] = counts.get(category, 0) + 1
    prominent = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    labels = []
    for category, count in prominent:
        label = next(
            (
                str(event.get("category_label"))
                for event in events
                if event.get("category") == category and event.get("category_label")
            ),
            category,
        )
        labels.append(f"{label} ({count})")
    return [
        "Son KAP/kurumsal olay akışında "
        + ", ".join(labels)
        + " öne çıkıyor; olay türü tek başına olumlu/olumsuz yön olarak yorumlanmıyor."
    ]


def _integrated_synthesis(
    *,
    technical: Mapping[str, Any],
    fundamental: Mapping[str, Any],
    peer: Mapping[str, Any],
    valuation: Mapping[str, Any],
    corporate_events: list[Mapping[str, Any]],
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
    context.extend(_corporate_context(corporate_events))

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
            "corporate_event_category_is_not_sentiment": True,
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
        corporate_events=events,
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
            "corporate_event_type_is_not_direction": True,
        },
    }
    return to_primitive(report)


def _fmt_metric(metric: str, value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if metric in _PERCENT_METRICS:
        return f"%{number * 100:.1f}"
    if metric in _MULTIPLE_METRICS:
        return f"{number:.2f}x"
    return f"{number:.2f}"


def _fmt_delta(metric: str, value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if metric in _PERCENT_METRICS:
        return f"{number * 100:+.1f} puan"
    if metric in _MULTIPLE_METRICS:
        return f"{number:+.2f}x"
    return f"{number:+.2f}"


def _scope_text(item: Mapping[str, Any]) -> str:
    scope = str(item.get("scope") or "")
    if scope == "INDUSTRY_PEER_GROUP":
        return "doğrudan eş grup"
    if scope == "PROVIDER_SECTOR_FALLBACK":
        label = str(item.get("benchmark_label") or "aynı sektör")
        return f"{label} sektörü"
    if scope == "BROAD_SECTOR_FALLBACK":
        return "geniş analiz ailesi"
    return "karşılaştırma grubu"


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
    context = list(synthesis.get("context") or [])
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
            metric = str(item.get("metric") or "")
            delta = _fmt_delta(metric, item.get("delta_to_median"))
            delta_text = f" · medyana fark {delta}" if delta else ""
            lines.append(
                f"• {item.get('metric_label')}: şirket {_fmt_metric(metric, item.get('target_value'))} · "
                f"medyan {_fmt_metric(metric, item.get('peer_median'))}{delta_text} · "
                f"{_POSITION_TR.get(str(item.get('position')), item.get('position'))} · "
                f"{_FAVOURABILITY_TR.get(str(item.get('favourability')), item.get('favourability'))} · "
                f"{_scope_text(item)}"
            )

    events = list(report.get("corporate_events") or [])
    if events:
        lines.extend(["", "Son KAP / kurumsal gelişmeler:"])
        for event in events[:5]:
            published = str(event.get("published_at") or "").replace("T", " ")[:16]
            date_prefix = f"{published} · " if published else ""
            lines.append(
                f"• {date_prefix}{event.get('category_label') or event.get('category')}: {event.get('title')}"
            )
        lines.append("• KAP olay türleri tek başına olumlu/olumsuz sinyal kabul edilmez; içerik ve büyüklük ayrıca incelenir.")

    if context:
        lines.extend(["", "Bağlam:", *[f"• {item}" for item in context[:4]]])

    lines.extend(
        [
            "",
            "Not: Teknik, temel, değerleme, sektör ve kurumsal olaylar ayrı kanıt eksenleridir; otomatik AL/SAT veya tek puan üretilmez.",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "EQUITY_REPORT_SCHEMA",
    "build_equity_report_contract",
    "format_equity_report_preview",
]
