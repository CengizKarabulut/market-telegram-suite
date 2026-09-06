"""Shared deterministic paragraph helpers for the rich /analiz commentary engine.

This module intentionally does not expose a second commentary composer. The single
user-facing compose/message path lives in ``research_commentary_rich.py``.
"""

from __future__ import annotations

import math
from typing import Any

from src.research_engine import ResearchDimension, ResearchReport


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _num(value: Any, digits: int = 1) -> str:
    number = _finite(value)
    return "—" if number is None else f"{number:.{digits}f}"


def _pct(value: Any, digits: int = 1) -> str:
    number = _finite(value)
    return "—" if number is None else f"%{number:.{digits}f}"


def _dimension(report: ResearchReport, name: str) -> ResearchDimension | None:
    target = name.casefold()
    return next((item for item in report.dimensions if item.name.casefold() == target), None)


def _score_phrase(item: ResearchDimension | None) -> str:
    if item is None or item.score is None:
        return "bu başlıkta güvenilir puan üretmek için veri kapsamı yeterli değil"
    return f"{item.score:.0f}/100 puanla {item.label.casefold()} görünüm veriyor"


def _company_paragraph(report: ResearchReport) -> str:
    quality = _dimension(report, "Şirket Kalitesi")
    profile = {"BANK": "banka", "GYO": "GYO", "GENERIC": "şirket"}.get(
        report.profile,
        "şirket",
    )
    return (
        f"{report.symbol} için şirket kalitesi {_score_phrase(quality)}. Değerlendirme {profile} profiline göre "
        "kârlılık, büyüme, bilanço/sermaye ve nakit göstergelerinden türetiliyor; değerleme bu puana ikinci kez "
        f"katılmıyor. Toplam araştırma veri kapsamı %{round(report.coverage * 100)}; eksik alanlar nötr veya "
        "olumsuz varsayılmak yerine veri yetersiz bırakılıyor."
    )


def _balance_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    label = str(financial.get("balance_label", "VERİ YETERSİZ"))
    score = _finite(financial.get("balance_score"))
    score_text = "" if score is None else f" ve puan {score:.0f}/100"
    if report.profile == "BANK":
        return (
            f"Bilanço trendi {label.casefold()} olarak sınıflanıyor{score_text}. Aktif büyümesi "
            f"{_pct(metrics.get('assets_growth'))}, özkaynak büyümesi {_pct(metrics.get('equity_growth'))}, net kâr "
            f"büyümesi {_pct(metrics.get('net_income_growth'))} ve kredi/mevduat oranı "
            f"{_num(metrics.get('loans_deposits'), 2)}. Resmî SYR, NPL ve karşılık oranları yoksa yorum yalnız "
            "erişilebilen banka bilanço verileriyle sınırlı tutuluyor."
        )
    return (
        f"Bilanço trendi {label.casefold()}{score_text}. TTM satış büyümesi {_pct(metrics.get('revenue_growth'))}, "
        f"faaliyet kârı büyümesi {_pct(metrics.get('operating_growth'))}, faaliyet marjı değişimi "
        f"{_num(metrics.get('operating_margin_yoy_change_pp'))} puan ve cari oran "
        f"{_num(metrics.get('current_ratio'), 2)}. Yorum tek çeyrek yerine son sekiz çeyrek/TTM eğilimini esas alıyor; "
        "büyüme, marj, likidite ve borç yönü birlikte okunuyor."
    )


def _earnings_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    quality = _dimension(report, "Kâr Kalitesi")
    if quality is None or quality.score is None:
        return (
            "Kâr kalitesi için yeterli veri kapsamı oluşmadığından yapay bir puan üretilmiyor. Nakit akım tablosu, "
            "CFO/net kâr, serbest nakit akışı veya tahakkuk göstergeleri eksikse yüksek görünen muhasebe kârı "
            "otomatik olarak kaliteli kabul edilmiyor."
        )
    if report.profile == "BANK":
        return (
            f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. Net faiz geliri büyümesi "
            f"{_pct(metrics.get('net_interest_growth'))}, ROE {_pct(metrics.get('roe'))}, faaliyet gideri büyümesi "
            f"{_pct(metrics.get('operating_expense_growth'))} ve net kâr büyümesi "
            f"{_pct(metrics.get('net_income_growth'))} birlikte değerlendiriliyor. Bankalarda klasik CFO/net kâr "
            "yaklaşımı yerine faiz geliri, özkaynak kârlılığı ve gider disiplini ağırlık kazanıyor."
        )
    return (
        f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. CFO/net kâr "
        f"{_num(metrics.get('cfo_net_income'), 2)}x, FCF marjı {_pct(metrics.get('fcf_margin'))}, tahakkuk oranı "
        f"{_pct(metrics.get('accrual_ratio'))}; alacak-satış büyüme farkı "
        f"{_num(metrics.get('receivables_vs_sales_gap'))} puan ve stok-satış farkı "
        f"{_num(metrics.get('inventory_vs_sales_gap'))} puan. Net kârın nakde dönüşmemesi veya işletme sermayesinin "
        "satışlardan hızlı şişmesi kaliteyi aşağı çeken temel işaretlerdir."
    )


def _debt_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    if report.profile == "BANK":
        return (
            "Bankalarda klasik net borç/FAVÖK yaklaşımı ekonomik olarak anlamlı olmadığı için borç bölümü şirketler "
            f"gibi yazılmıyor. Kredi/mevduat {_num(metrics.get('loans_deposits'), 2)}, özkaynak/aktif "
            f"{_pct(metrics.get('equity_assets'))}. Resmî sermaye yeterliliği verisi yoksa vekil oranlar resmî SYR "
            "gibi sunulmuyor."
        )
    return (
        f"Borç ve nakit yönü {str(financial.get('debt_direction', 'VERİ YETERSİZ')).casefold()}. Net borç/FAVÖK "
        f"{_num(metrics.get('net_debt_ebitda'), 2)}x, net borç/özkaynak "
        f"{_num(metrics.get('net_debt_equity'), 2)}x, net borç değişimi "
        f"{_pct(metrics.get('net_debt_yoy_change'))} ve faiz karşılama "
        f"{_num(metrics.get('interest_coverage'), 2)}x. Borcun nominal tutarından çok faaliyet kârı ve nakit yaratımı "
        "karşısındaki taşınabilirliği ile yönü esas alınıyor."
    )


def _valuation_paragraph(report: ResearchReport) -> str:
    valuation = report.valuation
    dimension = _dimension(report, "Değerleme")
    if dimension is None or dimension.score is None:
        return (
            "Değerleme tarafında yeterli karşılaştırılabilir çarpan bulunmadığı için ucuz/pahalı hükmü üretilmiyor. "
            "Eksik veya negatif paydalı çarpanlar puana zorla sokulmuyor."
        )
    names = {
        "pe": "F/K",
        "pb": "PD/DD",
        "ev_ebitda": "FD/FAVÖK",
        "ev_sales": "FD/Satış",
        "dividend_yield": "Temettü",
    }
    parts: list[str] = []
    for key, label in names.items():
        item = valuation.get("metrics", {}).get(key, {})
        value = _finite(item.get("value")) if isinstance(item, dict) else None
        percentile = _finite(item.get("percentile")) if isinstance(item, dict) else None
        if value is not None and percentile is not None:
            parts.append(f"{label} {_num(value, 2)} (yüzdelik %{percentile:.0f})")
    metrics_text = "; ".join(parts[:4]) or "karşılaştırılabilir çarpan sayısı sınırlı"
    extra = ""
    if report.profile == "GYO":
        extra = " GYO için gerçek NAD/NAV yoksa PD/NAD analizi yapılamadığı ayrıca belirtiliyor."
    elif report.profile == "BANK":
        extra = " Bankada FD/FAVÖK kullanılmıyor; F/K ve PD/DD öncelikli tutuluyor."
    return (
        f"Değerleme {dimension.score:.0f}/100 ile {dimension.label.casefold()} ve karşılaştırma evreni "
        f"{valuation.get('scope', '—')}. Başlıca veriler: {metrics_text}. Puan, çarpanın mutlak sayısından çok benzer "
        "şirketler içindeki göreli konumuna bakıyor; düşük çarpan otomatik olarak kalite sinyali sayılmıyor." + extra
    )


def _levels_paragraph(report: ResearchReport) -> str:
    if report.supports:
        support = report.supports[0]
        support_text = (
            f"en yakın destek {support.low:.2f}–{support.high:.2f}, Q{support.score:.0f}, "
            f"{support.distance_atr:.1f} ATR uzakta ve {support.status.casefold()}"
        )
    else:
        support_text = "fiyatın altında yeterli kalite ve yakınlık koşulunu sağlayan aktif destek yok"
    if report.resistances:
        resistance = report.resistances[0]
        resistance_text = (
            f"en yakın direnç {resistance.low:.2f}–{resistance.high:.2f}, Q{resistance.score:.0f}, "
            f"{resistance.distance_atr:.1f} ATR uzakta ve {resistance.status.casefold()}"
        )
    else:
        resistance_text = "fiyatın üstünde yeterli kalite ve yakınlık koşulunu sağlayan aktif direnç yok"
    return (
        f"Kritik seviyelerde {support_text}; {resistance_text}. Seviye yönü güncel fiyata göre kontrol ediliyor; "
        "fiyatın üstündeki bölge aktif destek, fiyatın altındaki bölge aktif direnç olarak gösterilmiyor. Kırılan bölgeler "
        "rol değişimiyle yeniden sınıflandırılıyor, uzak/eski seviyeler karar seviyesine taşınmıyor."
    )


def _risk_paragraph(report: ResearchReport) -> str:
    if report.main_risk is None:
        return (
            "Mevcut kanıt setinde 35/100 eşiğini aşan tek bir baskın risk oluşmuyor. Bu risk olmadığı anlamına gelmiyor; "
            "yalnız veriyle doğrulanmış risklerin birbirinden belirgin ayrışmadığını gösteriyor. Eksik veri ayrıca risk gibi "
            "puanlanmıyor."
        )
    others = [item for item in report.risks if item.name != report.main_risk.name][:2]
    secondary = "; ".join(f"{item.name} {item.score:.0f}/100" for item in others)
    suffix = f" İkincil riskler: {secondary}." if secondary else ""
    return (
        f"Ana risk {report.main_risk.name} ve risk puanı {report.main_risk.score:.0f}/100. Dayanak: "
        f"{report.main_risk.evidence} Risk sıralaması finansal kaldıraç, kâr kalitesi, değerleme hassasiyeti, teknik yapı "
        "ve likiditeyi birlikte tarıyor; veri olmayan başlık nötr risk gibi uydurulmuyor." + suffix
    )


def _conclusion_paragraph(report: ResearchReport) -> str:
    scored = [item for item in report.dimensions if item.score is not None]
    strongest = max(scored, key=lambda item: item.score) if scored else None
    weakest = min(scored, key=lambda item: item.score) if scored else None
    strong_text = (
        "belirgin güçlü boyut yok"
        if strongest is None
        else f"en güçlü taraf {strongest.name} ({strongest.score:.0f}/100)"
    )
    weak_text = (
        "belirgin zayıf boyut yok"
        if weakest is None
        else f"en zayıf taraf {weakest.name} ({weakest.score:.0f}/100)"
    )
    risk_text = (
        "baskın tek risk yok"
        if report.main_risk is None
        else f"ana risk {report.main_risk.name}"
    )
    score_text = "—" if report.research_score is None else f"{report.research_score:.0f}/100"
    return (
        f"Genel araştırma skoru {score_text}; {strong_text}, {weak_text} ve {risk_text}. Sonuç tek bir göstergeye değil "
        "teknik yapı, bilanço, kâr kalitesi, borç/nakit, değerleme ve risk kanıtlarının birlikte okunmasına dayanıyor. "
        "Bu çıktı otomatik işlem çağrısı değil; hangi olumlu tezlerin hangi risk ve seviyelerle sınandığını gösteren karar "
        "desteğidir."
    )
