"""Single production pipeline shared by Telegram, health checks and manual tools."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.financial_intelligence_card import render_financial_intelligence_card
from src.fundamental_card import render_fundamental_card
from src.moving_average_card import render_moving_average_card
from src.research_card import render_research_card
from src.research_chart import render_research_chart
from src.research_commentary_rich import compose_research_commentary
from src.research_theme import apply_white_theme
from src.research_v2 import build_research_report
from src.valuation_peer_card import render_valuation_peer_card

TECHNICAL_SECTION_TITLES = (
    "TEKNİK YAPI NE DİYOR?",
    "KRİTİK SEVİYELER NEREDE?",
    "TEKNİK RİSK NE?",
)


@dataclass(frozen=True)
class ResearchBundle:
    report: object
    root: Path
    summary_card: Path
    fundamental_card: Path
    financial_card: Path
    valuation_peer_card: Path
    moving_average_card: Path
    technical_chart: Path
    json_path: Path
    commentary_path: Path
    moving_averages: dict

    @property
    def visuals(self) -> tuple[Path, ...]:
        return (
            self.summary_card,
            self.fundamental_card,
            self.financial_card,
            self.valuation_peer_card,
            self.moving_average_card,
            self.technical_chart,
        )


@dataclass(frozen=True)
class TechnicalBundle:
    """Modern technical-only output; never falls back to the legacy dashboard."""

    report: object
    root: Path
    moving_average_card: Path
    technical_chart: Path
    json_path: Path
    commentary_path: Path
    moving_averages: dict

    @property
    def visuals(self) -> tuple[Path, ...]:
        return (self.moving_average_card, self.technical_chart)


def _write_commentary(root: Path, ticker: str, sections: tuple[tuple[str, str], ...], suffix: str) -> Path:
    text = "\n\n".join(f"{title}\n{paragraph}" for title, paragraph in sections)
    path = root / f"{ticker}_{suffix}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _technical_risk_paragraph(report) -> str:
    technical = report.technical
    structure = technical.get("structure", {})
    weekly = technical.get("weekly_structure", {})
    atr_pct = technical.get("atr_pct")
    divergence = technical.get("latest_rsi_divergence")
    divergence_text = divergence.get("kind") if isinstance(divergence, dict) else "yok"
    score = technical.get("score")
    score_text = "—" if score is None else f"{float(score):.0f}/100"
    atr_text = "—" if atr_pct is None else f"%{float(atr_pct):.1f}"

    if report.supports:
        nearest_support = report.supports[0]
        support_text = (
            f"en yakın aktif destek {nearest_support.low:.2f}–{nearest_support.high:.2f} ve "
            f"{nearest_support.distance_atr:.1f} ATR uzakta"
        )
    else:
        support_text = "fiyat altında yakın ve yeterli kaliteye sahip aktif destek bulunmuyor"

    if report.resistances:
        nearest_resistance = report.resistances[0]
        resistance_text = (
            f"en yakın direnç {nearest_resistance.low:.2f}–{nearest_resistance.high:.2f} ve "
            f"{nearest_resistance.distance_atr:.1f} ATR uzakta"
        )
    else:
        resistance_text = "yakın aktif direnç bulunmuyor"

    return (
        f"Teknik risk değerlendirmesinde teknik skor {score_text}; günlük yapı {structure.get('state', '—')} / "
        f"{structure.get('event', structure.get('bos', '—'))}, haftalık yapı {weekly.get('state', '—')} / "
        f"{weekly.get('event', '—')}. ATR {atr_text}, AlphaTrend {technical.get('alpha_trend_state', '—')} ve son "
        f"RSI uyumsuzluğu {divergence_text}. Seviye tarafında {support_text}; {resistance_text}. Bu bölüm yalnız "
        "fiyat yapısı, momentum, volatilite ve seviye yaşam döngüsünden doğan riski anlatır; değerleme veya bilanço "
        "riski teknik-only rapora karıştırılmaz."
    )


def technical_commentary_sections(report) -> tuple[tuple[str, str], ...]:
    """Return a strictly technical interpretation stack for the manual technical mode."""
    section_map = dict(compose_research_commentary(report))
    return (
        ("TEKNİK YAPI NE DİYOR?", section_map["TEKNİK YAPI NE DİYOR?"]),
        ("KRİTİK SEVİYELER NEREDE?", section_map["KRİTİK SEVİYELER NEREDE?"]),
        ("TEKNİK RİSK NE?", _technical_risk_paragraph(report)),
    )


def build_research_bundle(symbol: str, target: str | Path) -> ResearchBundle:
    """Build one deterministic full research bundle with all cards and machine output."""
    apply_white_theme()
    ticker = symbol.strip().upper().removesuffix(".IS")
    root = Path(target)
    root.mkdir(parents=True, exist_ok=True)

    report = build_research_report(ticker)
    summary = render_research_card(report, root / f"{ticker}_arastirma.png")
    fundamental = render_fundamental_card(report.fundamental, root / f"{ticker}_temel.png")
    financial = render_financial_intelligence_card(report, root / f"{ticker}_finansal_oranlar.png")
    valuation = render_valuation_peer_card(report, root / f"{ticker}_degerleme_rakipler.png")
    moving_average, ma_snapshot = render_moving_average_card(ticker, root / f"{ticker}_ortalamalar.png")
    technical = render_research_chart(ticker, report, root / f"{ticker}_teknik_yapi.png")

    commentary = compose_research_commentary(report)
    commentary_path = _write_commentary(root, ticker, commentary, "yorum")

    payload = report.to_dict()
    payload["moving_averages"] = ma_snapshot
    payload["commentary"] = dict(commentary)
    json_path = root / f"{ticker}_arastirma.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return ResearchBundle(
        report=report,
        root=root,
        summary_card=summary,
        fundamental_card=fundamental,
        financial_card=financial,
        valuation_peer_card=valuation,
        moving_average_card=moving_average,
        technical_chart=technical,
        json_path=json_path,
        commentary_path=commentary_path,
        moving_averages=ma_snapshot,
    )


def build_technical_bundle(symbol: str, target: str | Path) -> TechnicalBundle:
    """Build the new technical-only package from the same audited research engine.

    The legacy ``stock_dashboard`` report is intentionally not used. The user-facing
    package contains the white MA table, the Pine-faithful 16:9 technical chart and
    interpretation-only technical/levels/risk paragraphs.
    """
    apply_white_theme()
    ticker = symbol.strip().upper().removesuffix(".IS")
    root = Path(target)
    root.mkdir(parents=True, exist_ok=True)

    report = build_research_report(ticker)
    moving_average, ma_snapshot = render_moving_average_card(ticker, root / f"{ticker}_ortalamalar.png")
    technical = render_research_chart(ticker, report, root / f"{ticker}_teknik_yapi.png")

    sections = technical_commentary_sections(report)
    commentary_path = _write_commentary(root, ticker, sections, "teknik_yorum")

    payload = {
        "symbol": ticker,
        "price": report.price,
        "technical": report.technical,
        "supports": [zone.__dict__ for zone in report.supports],
        "resistances": [zone.__dict__ for zone in report.resistances],
        "moving_averages": ma_snapshot,
        "commentary": dict(sections),
        "note": "Yeni araştırma motorunun teknik-only görünümüdür; eski stock_dashboard içeriği kullanılmaz.",
    }
    json_path = root / f"{ticker}_teknik.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return TechnicalBundle(
        report=report,
        root=root,
        moving_average_card=moving_average,
        technical_chart=technical,
        json_path=json_path,
        commentary_path=commentary_path,
        moving_averages=ma_snapshot,
    )
