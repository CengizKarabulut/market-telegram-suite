from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_core.equity_report import build_equity_report_contract
from market_core.reader_presentation import format_reader_telegram
from src.telegram_client import send_text


VALUATION_METRICS = (
    "pe",
    "price_to_book",
    "ev_to_ebitda",
    "price_to_sales",
    "price_to_nav",
    "nav_discount",
)
VALUATION_LABELS = {
    "pe": "F/K",
    "price_to_book": "F/DD",
    "ev_to_ebitda": "FD/FAVÖK",
    "price_to_sales": "Fiyat/Satışlar",
    "price_to_nav": "Fiyat/NAD",
    "nav_discount": "NAD iskontosu",
}


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, Mapping) else {}


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _contextual_valuation(peer_payload: Mapping[str, Any]) -> dict[str, Any]:
    metrics = peer_payload.get("target_metrics") or {}
    selected: dict[str, float] = {}
    for name in VALUATION_METRICS:
        value = _finite(metrics.get(name)) if isinstance(metrics, Mapping) else None
        if value is None:
            continue
        if name in {"pe", "price_to_book", "ev_to_ebitda", "price_to_sales", "price_to_nav"} and value <= 0:
            continue
        selected[name] = value
    return {
        "available": bool(selected),
        "basis": "TRADINGVIEW_SPOT_CONTEXTUAL_MULTIPLES",
        "metrics": selected,
        "intrinsic_value_available": False,
        "automatic_cheap_expensive_label": False,
        "limitations": [
            "Çarpanlar bağlamsal karşılaştırmadır; tek başına ucuz/pahalı kararı değildir.",
            "İçsel değer/fiyat hedefi üretilmez.",
        ],
    }


def _technical_paragraph(technical: Mapping[str, Any]) -> str:
    if not technical:
        return "Teknik tarafta güvenilir değerlendirme üretilemedi."
    text = format_reader_telegram(dict(technical))
    if "\n\n" in text:
        return text.split("\n\n", 1)[1].strip()
    return text.strip()


def _compact(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _dedupe(sentences: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        cleaned = _compact(sentence)
        if not cleaned:
            continue
        key = re.sub(r"[^a-z0-9çğıöşü]+", " ", cleaned.casefold()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _fundamental_sentences(current: Mapping[str, Any]) -> list[str]:
    if not current.get("available"):
        reason = _compact(current.get("reason"))
        return [
            "Temel analiz tarafında doğrulanmış güncel finansal veri sınırlı olduğu için bu eksen yoruma tam olarak dahil edilemiyor."
            + (f" ({reason})" if reason else "")
        ]
    synthesis = current.get("synthesis") or {}
    sentences = [_compact(synthesis.get("headline"))]
    sentences.extend(_compact(item) for item in (synthesis.get("positives") or [])[:2])
    sentences.extend(_compact(item) for item in (synthesis.get("risks") or [])[:2])
    return _dedupe(sentences)


def _peer_sentences(peer_payload: Mapping[str, Any], limit: int = 3) -> list[str]:
    benchmark = peer_payload.get("benchmark") or {}
    if not benchmark.get("available"):
        return ["Sağlıklı sektör/eş şirket karşılaştırması için yeterli ortak veri bulunamadı."]
    metrics = benchmark.get("metrics") or {}
    rows: list[tuple[int, str]] = []
    priority = {"FAVOURABLE": 0, "UNFAVOURABLE": 1, "CONTEXTUAL": 2, "NEUTRAL": 3}
    for metric in metrics.values() if isinstance(metrics, Mapping) else []:
        if not isinstance(metric, Mapping) or not metric.get("available"):
            continue
        comment = _compact(metric.get("comment"))
        if not comment:
            continue
        rows.append((priority.get(str(metric.get("favourability") or ""), 9), comment))
    rows.sort(key=lambda item: item[0])
    return _dedupe([comment for _, comment in rows[:limit]])


def _valuation_sentence(valuation: Mapping[str, Any]) -> str:
    if not valuation.get("available"):
        return "Değerleme tarafında sağlıklı ve karşılaştırılabilir güncel çarpan verisi bulunmadığı için bu eksende kesin yorum yapılmıyor."
    metrics = valuation.get("metrics") or {}
    visible: list[str] = []
    for name in VALUATION_METRICS:
        value = _finite(metrics.get(name)) if isinstance(metrics, Mapping) else None
        if value is None:
            continue
        label = VALUATION_LABELS.get(name, name)
        if name == "nav_discount":
            visible.append(f"{label} %{value * 100:.1f}".replace(".", ","))
        else:
            visible.append(f"{label} {value:.2f}x".replace(".", ","))
        if len(visible) >= 3:
            break
    if not visible:
        return ""
    return (
        "Güncel değerleme bağlamında "
        + ", ".join(visible)
        + " izleniyor; bu çarpanların düşük veya yüksek olması tek başına ucuzluk ya da pahalılık kararı sayılmıyor."
    )


def _event_sentence(events: list[Mapping[str, Any]]) -> str:
    if not events:
        return ""
    recent = events[:2]
    titles = [_compact(item.get("title")) for item in recent if _compact(item.get("title"))]
    if not titles:
        return ""
    joined = "; ".join(titles)
    return (
        f"Son KAP akışında {joined} başlıkları öne çıkıyor; bu bildirimlerin türü tek başına olumlu veya olumsuz fiyat sinyali sayılmıyor."
    )


def _final_sentence(report: Mapping[str, Any]) -> str:
    synthesis = report.get("integrated_synthesis") or {}
    state = str(synthesis.get("state") or "")
    if state == "CROSS_AXIS_CONFLICT":
        return "Sonuç olarak teknik, temel ve sektör verileri aynı yönde birleşmediği için teyit almadan tek yönlü hüküm vermek doğru değil."
    if state == "MULTI_AXIS_POSITIVE":
        return "Sonuç olarak birden fazla analiz ekseni olumlu yönde birleşiyor; yine de fiyatın kritik seviyelerdeki davranışı teyit açısından izlenmeli."
    if state == "MULTI_AXIS_RISK":
        return "Sonuç olarak riskler birden fazla analiz ekseninde öne çıkıyor; toparlanma için hem fiyat davranışında hem de temel göstergelerde iyileşme görmek gerekiyor."
    if state == "MIXED":
        return "Sonuç olarak hissede güçlü ve zayıf taraflar birlikte bulunuyor; tek bir göstergeye veya çarpana bakarak karar vermek yeterli değil."
    return "Sonuç olarak mevcut veriler tek yönlü ve güçlü bir ortak teyit üretmiyor; yeni fiyat ve finansal verilerle görünüm yeniden değerlendirilmelidir."


def format_application_text(report: Mapping[str, Any]) -> str:
    technical = report.get("technical") or {}
    symbol = str(report.get("symbol") or "—")
    interval = str(technical.get("interval_label") or technical.get("interval") or "")
    price = _finite(technical.get("price"))
    change = _finite(technical.get("change_pct"))
    price_text = f"{price:.2f}".replace(".", ",") if price is not None else "—"
    change_text = f"{change:+.2f}%".replace(".", ",") if change is not None else "—"

    fundamental = (report.get("fundamental") or {}).get("current_period") or {}
    peer_block = (report.get("sector_and_peers") or {}).get("benchmark") or {}
    peer_payload = {"benchmark": peer_block}
    valuation = report.get("valuation") or {}
    events = list(report.get("corporate_events") or [])

    parts = [_technical_paragraph(technical)]
    parts.extend(_fundamental_sentences(fundamental))
    parts.extend(_peer_sentences(peer_payload))
    valuation_text = _valuation_sentence(valuation)
    if valuation_text:
        parts.append(valuation_text)
    event_text = _event_sentence(events)
    if event_text:
        parts.append(event_text)
    parts.append(_final_sentence(report))
    paragraph = " ".join(_dedupe(parts))

    return "\n".join(
        [
            f"{symbol} — Bütünleşik Analist Görüşü" + (f" ({interval})" if interval else ""),
            f"Fiyat: {price_text} · Değişim: {change_text}",
            "",
            paragraph,
        ]
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="V4 uygulama: teknik + temel + sektör + KAP sentezi")
    parser.add_argument("symbol")
    parser.add_argument("--technical", required=True)
    parser.add_argument("--fundamental-probe", required=True)
    parser.add_argument("--peer", required=True)
    parser.add_argument("--output", default="reports/v4_equity_app")
    parser.add_argument("--telegram", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.strip().upper().removesuffix(".IS").removesuffix(".E")
    technical = _load(Path(args.technical))
    fundamental_probe = _load(Path(args.fundamental_probe))
    peer_payload = _load(Path(args.peer))
    current_fundamental = fundamental_probe.get("current_analysis") or {}
    timeline = fundamental_probe.get("corporate_events") or {}
    events = list(timeline.get("events") or []) if isinstance(timeline, Mapping) else []
    benchmark = peer_payload.get("benchmark") or {}
    valuation = _contextual_valuation(peer_payload)

    report = build_equity_report_contract(
        symbol=symbol,
        technical_report=technical,
        current_fundamental_view=current_fundamental,
        valuation_state=valuation,
        peer_benchmark=benchmark,
        corporate_events=events,
    )
    text = format_application_text(report)

    target = Path(args.output) / symbol
    target.mkdir(parents=True, exist_ok=True)
    report_path = target / f"{symbol}_equity_report_v4.json"
    text_path = target / f"{symbol}_analyst_v4.txt"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(text + "\n", encoding="utf-8")

    if args.telegram:
        send_text(text)
        print("Telegram: V4 bütünleşik analist paragrafı gönderildi.")

    print(text)
    print(f"Equity report: {report_path}")
    print(f"Analyst text: {text_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
