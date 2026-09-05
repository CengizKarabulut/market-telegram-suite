from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tradingview_screener import stocks

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_core.peer_benchmarks import build_hierarchical_peer_benchmark  # noqa: E402
from market_core.sector_profiles import profile_for_sector  # noqa: E402
from market_core.tradingview_peers import (  # noqa: E402
    TRADINGVIEW_FIELDS,
    observations_from_tradingview_frame,
)


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
    "ABOVE_MEDIAN": "medyan üstü",
    "AT_MEDIAN": "medyan civarı",
    "BELOW_MEDIAN": "medyan altı",
    "BOTTOM_QUARTILE": "alt çeyrek",
}

_FAVOURABILITY_TR = {
    "FAVOURABLE": "göreli olumlu",
    "UNFAVOURABLE": "göreli zayıf",
    "NEUTRAL": "nötr",
    "CONTEXTUAL": "bağlamsal",
}


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _metric_label(sector_type: Any, name: str) -> str:
    profile = profile_for_sector(sector_type)
    for rule in profile.metric_rules:
        if rule.metric == name:
            return rule.label
    return name


def _format_number(name: str, value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if name in _PERCENT_METRICS:
        return f"%{number * 100:.1f}"
    if name in _MULTIPLE_METRICS:
        return f"{number:.2f}x"
    return f"{number:.2f}"


def _summary_text(observation: Any, benchmark: dict[str, Any]) -> str:
    profile = profile_for_sector(observation.sector_type)
    metadata = observation.metadata
    synthesis = benchmark.get("synthesis") or {}
    lines = [
        f"{observation.symbol} — Sektör / Eş Şirket Karşılaştırması",
        (
            f"Analiz ailesi: {profile.label} · Eş grup: {benchmark.get('preferred_peer_group')} · "
            f"Sektör: {metadata.get('sector') or '—'} · Alt sektör: {metadata.get('industry') or '—'}"
        ),
        str(synthesis.get("headline") or "Karşılaştırma özeti üretilemedi."),
        "",
        "Öne çıkan karşılaştırmalar:",
    ]

    available = [
        (name, metric)
        for name, metric in (benchmark.get("metrics") or {}).items()
        if metric.get("available")
    ]
    priority = {"FAVOURABLE": 0, "UNFAVOURABLE": 1, "CONTEXTUAL": 2, "NEUTRAL": 3}
    available.sort(
        key=lambda item: (
            priority.get(str(item[1].get("favourability")), 9),
            item[0],
        )
    )
    for name, metric in available[:8]:
        scope = (
            "eş grup"
            if metric.get("scope") == "INDUSTRY_PEER_GROUP"
            else "geniş sektör (eş grup verisi yetersiz)"
        )
        lines.append(
            "• "
            f"{_metric_label(observation.sector_type, name)}: "
            f"şirket {_format_number(name, metric.get('target_value'))} · "
            f"medyan {_format_number(name, metric.get('peer_median'))} · "
            f"ortalama {_format_number(name, metric.get('peer_mean'))} · "
            f"{_POSITION_TR.get(str(metric.get('position')), metric.get('position'))} · "
            f"{_FAVOURABILITY_TR.get(str(metric.get('favourability')), metric.get('favourability'))} · "
            f"{scope}"
        )

    if not available:
        lines.append("• Sağlıklı karşılaştırma için yeterli ortak metrik/eş şirket bulunamadı.")

    fallback_metrics = benchmark.get("fallback_metrics") or []
    if fallback_metrics:
        lines.extend(
            [
                "",
                "Veri kapsamı notu:",
                (
                    "• Bazı metriklerde alt sektör/eş grup örneklemi yetersiz olduğu için geniş sektör "
                    "karşılaştırması açıkça işaretlenerek kullanıldı."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "Yorum kuralı:",
            "• Ortalama tek başına kullanılmaz; medyan ve çeyrekler ana referanstır.",
            (
                "• F/K, F/DD, FD/FAVÖK gibi çarpanlarda düşük/yüksek konum otomatik olarak ucuz/pahalı "
                "kararı değildir."
            ),
            "• Aynı metrik farklı dönem/baz ile raporlanıyorsa karşılaştırma grubundan çıkarılır.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 BIST sektör/eş şirket karşılaştırma probu")
    parser.add_argument("symbols", nargs="+", help="Karşılaştırılacak BIST sembolleri")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", default="reports/v4_peer_universe")
    args = parser.parse_args()

    if args.limit < 100:
        parser.error("--limit en az 100 olmalıdır; sektör örneklemi aksi halde eksik kalabilir")

    symbols = [item.strip().upper().removesuffix(".IS").removesuffix(".E") for item in args.symbols]
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    total, frame = (
        stocks("turkey")
        .select(*TRADINGVIEW_FIELDS)
        .limit(args.limit)
        .get_scanner_data()
    )
    frame.to_csv(output_dir / "bist_peer_universe.csv", index=False, encoding="utf-8-sig")
    observations = observations_from_tradingview_frame(frame)
    observation_by_symbol = {item.symbol: item for item in observations}

    universe_payload = {
        "provider": "TradingView Screener",
        "reported_total": total,
        "rows_returned": len(frame),
        "observations": len(observations),
        "fields": list(TRADINGVIEW_FIELDS),
        "classification_counts": {},
    }
    for observation in observations:
        key = observation.sector_type.value
        counts = universe_payload["classification_counts"]
        counts[key] = int(counts.get(key, 0)) + 1
    (output_dir / "universe_summary.json").write_text(
        json.dumps(universe_payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    results: dict[str, Any] = {}
    for symbol in symbols:
        target = observation_by_symbol.get(symbol)
        if target is None:
            results[symbol] = {
                "available": False,
                "reason": "Sembol TradingView Türkiye hisse evreninde bulunamadı.",
            }
            continue
        benchmark = build_hierarchical_peer_benchmark(
            target_symbol=symbol,
            peer_group=target.peer_group,
            sector_type=target.sector_type,
            observations=observations,
        )
        payload = {
            "available": benchmark.get("available"),
            "classification": {
                "symbol": target.symbol,
                "sector_type": target.sector_type.value,
                "peer_group": target.peer_group,
                "metadata": dict(target.metadata),
            },
            "target_metrics": dict(target.metrics),
            "target_metric_basis": dict(target.metric_basis),
            "benchmark": benchmark,
        }
        results[symbol] = payload
        symbol_dir = output_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        (symbol_dir / "peer_benchmark.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )
        (symbol_dir / "peer_summary.txt").write_text(
            _summary_text(target, benchmark),
            encoding="utf-8",
        )

    (output_dir / "peer_probe.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    print(
        f"TradingView BIST evreni: reported={total} · rows={len(frame)} · "
        f"observations={len(observations)}"
    )
    print(f"Sınıflar: {universe_payload['classification_counts']}")
    for symbol in symbols:
        result = results[symbol]
        if not result.get("available"):
            print(f"{symbol}: karşılaştırma kullanılamıyor · {result.get('reason')}")
            continue
        classification = result["classification"]
        benchmark = result["benchmark"]
        print(
            f"{symbol}: {classification['sector_type']} · {classification['peer_group']} · "
            f"{benchmark['synthesis']['state']} · fallback={benchmark['fallback_metrics']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
