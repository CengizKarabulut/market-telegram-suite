"""Deterministic paragraph commentary for the integrated research report.

The composer turns already-computed research evidence into short Turkish analyst
paragraphs. It never invents missing values and never emits automatic buy/sell
calls. The same report object therefore drives cards, charts and prose.
"""

from __future__ import annotations

from typing import Any

from src.research_engine import ResearchDimension, ResearchReport


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


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
    profile = {"BANK": "banka", "GYO": "GYO", "GENERIC": "şirket"}.get(report.profile, "şirket")
    coverage = f"%{round(report.coverage * 100)}"
    return (
        f"{report.symbol} için şirket kalitesi {_score_phrase(quality)}. Değerlendirme {profile} profiline göre "
        f"sektör uyarlamalı kârlılık, büyüme, bilanço/sermaye ve nakit göstergelerinden türetiliyor; değerleme "
        f"bu puanın içine ikinci kez katılmıyor. Toplam araştırma veri kapsamı {coverage}; bu nedenle eksik kalan "
        "alanlar nötr veya olumsuz varsayılmak yerine ayrıca veri yetersiz olarak bırakılıyor."
    )


def _balance_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    label = str(financial.get("balance_label", "VERİ YETERSİZ"))
    score = _finite(financial.get("balance_score"))
    if report.profile == "BANK":
        return (
            f"Bilanço trendi {label.casefold()} olarak sınıflanıyor"
            + (f" ve puan {score:.0f}/100" if score is not None else "")
            + f". Aktif büyümesi {_pct(metrics.get('assets_growth'))}, özkaynak büyümesi {_pct(metrics.get('equity_growth'))} "
            f"ve net kâr büyümesi {_pct(metrics.get('net_income_growth'))}; kredi/mevduat oranı {_num(metrics.get('loans_deposits'), 2)}. "
            "Resmî SYR, NPL ve karşılık oranları sağlayıcıda yoksa bu yorum yalnız erişilebilen bilanço kalemleriyle sınırlı tutuluyor."
        )
    return (
        f"Bilanço trendi {label.casefold()}"
        + (f" ve puan {score:.0f}/100" if score is not None else "")
        + f". TTM satış büyümesi {_pct(metrics.get('revenue_growth'))}, faaliyet kârı büyümesi {_pct(metrics.get('operating_profit_growth'))} "
        f"ve faaliyet marjı değişimi {_num(metrics.get('operating_margin_delta'))} puan; cari oran {_num(metrics.get('current_ratio'), 2)}. "
        "Yorum tek çeyrek yerine son sekiz çeyrek/TTM eğilimini esas alıyor; büyüme ile marj, likidite ve borç yönü birlikte okunuyor."
    )


def _earnings_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    quality = _dimension(report, "Kâr Kalitesi")
    if quality is None or quality.score is None:
        return (
            "Kâr kalitesi için yeterli veri kapsamı oluşmadığından yapay bir puan üretilmiyor. Özellikle nakit akım tablosu, "
            "CFO/net kâr, serbest nakit akışı veya tahakkuk göstergeleri eksikse yüksek görünen muhasebe kârı otomatik olarak "
            "kaliteli kabul edilmiyor; bu başlık veri tamamlanana kadar açık bırakılıyor."
        )
    if report.profile == "BANK":
        return (
            f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. Net faiz geliri büyümesi "
            f"{_pct(metrics.get('net_interest_growth'))}, ROE {_pct(metrics.get('roe'))}, faaliyet gideri büyümesi "
            f"{_pct(metrics.get('operating_expense_growth'))} ve net kâr büyümesi {_pct(metrics.get('net_income_growth'))} birlikte değerlendiriliyor. "
            "Bankalarda klasik CFO/net kâr yaklaşımı yerine faiz geliri, özkaynak kârlılığı ve gider disiplini ağırlık kazanıyor."
        )
    return (
        f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. CFO/net kâr oranı "
        f"{_num(metrics.get('cfo_net_income'), 2)}x, serbest nakit akışı marjı {_pct(metrics.get('fcf_margin'))} ve tahakkuk oranı "
        f"{_pct(metrics.get('accrual_ratio'))}. Alacakların satış büyümesinden farkı {_num(metrics.get('receivable_gap'))} puan, "
        f"stokların satış büyümesinden farkı {_num(metrics.get('inventory_gap'))} puan. Net kârın nakde dönüşmemesi veya işletme sermayesinin "
        "satışlardan hızlı şişmesi kâr kalitesini aşağı çeken temel işaretler olarak ele alınıyor."
    )


def _debt_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    if report.profile == "BANK":
        return (
            "Bankalarda klasik net borç/FAVÖK yaklaşımı ekonomik olarak anlamlı olmadığı için borç paragrafı şirketler gibi yazılmıyor. "
            f"Kredi/mevduat oranı {_num(metrics.get('loans_deposits'), 2)}, özkaynak/aktif oranı {_pct(metrics.get('equity_assets'))}; "
            "sermaye ve aktif-pasif dengesi ancak mevcut veri kapsamı ölçüsünde yorumlanıyor. Resmî sermaye yeterliliği verisi yoksa vekil oranlar resmî SYR gibi sunulmuyor."
        )
    return (
        f"Borç ve nakit tarafında yön {str(financial.get('debt_direction', 'VERİ YETERSİZ')).casefold()}. Net borç/FAVÖK "
        f"{_num(metrics.get('net_debt_ebitda'), 2)}x, net borç/özkaynak {_num(metrics.get('net_debt_equity'), 2)}x, net borç değişimi "
        f"{_pct(metrics.get('net_debt_change'))} ve faiz karşılama {_num(metrics.get('interest_coverage'), 2)}x. Borcun nominal tutarından çok "
        "faaliyet kârı ve nakit yaratımı karşısındaki taşınabilirliği ile yönü esas alınıyor."
    )


def _valuation_paragraph(report: ResearchReport) -> str:
    valuation = report.valuation
    dimension = _dimension(report, "Değerleme")
    if dimension is None or dimension.score is None:
        return (
            "Değerleme tarafında yeterli karşılaştırılabilir çarpan bulunmadığı için ucuz/pahalı hükmü üretilmiyor. "
            "Eksik veya negatif paydalı çarpanlar puana zorla sokulmuyor; sektör ve şirket profiline uygun veri oluşana kadar değerleme başlığı açık bırakılıyor."
        )
    metric_parts: list[str] = []
    names = {"pe": "F/K", "pb": "PD/DD", "ev_ebitda": "FD/FAVÖK", "ev_sales": "FD/Satış", "dividend_yield": "Temettü"}
    for key, label in names.items():
        item = valuation.get("metrics", {}).get(key, {})
        value = _finite(item.get("value")) if isinstance(item, dict) else None
        percentile = _finite(item.get("percentile")) if isinstance(item, dict) else None
        if value is not None and percentile is not None:
            metric_parts.append(f"{label} {_num(value, 2)} (yüzdelik %{percentile:.0f})")
    metrics_text = "; ".join(metric_parts[:4]) or "karşılaştırılabilir çarpan sayısı sınırlı"
    extra = ""
    if report.profile == "GYO":
        extra = " GYO için gerçek NAD/NAV verisi yoksa PD/NAD analizi yapılamadığı ve mevcut çarpan sonucunun sınırlı olduğu özellikle not ediliyor."
    elif report.profile == "BANK":
        extra = " Bankada FD/FAVÖK kullanılmıyor; F/K ve PD/DD öncelikli tutuluyor."
    return (
        f"Değerleme {dimension.score:.0f}/100 ile {dimension.label.casefold()} ve karşılaştırma evreni {valuation.get('scope', '—')}. "
        f"Mevcut başlıca veriler: {metrics_text}. Puan, çarpanın mutlak sayısından çok benzer şirketler içindeki göreli konumuna bakıyor; "
        "düşük çarpan otomatik olarak kalite sinyali sayılmıyor." + extra
    )


def _technical_paragraph(report: ResearchReport) -> str:
    technical = report.technical
    structure = technical.get("structure", {})
    weekly = technical.get("weekly_structure", {})
    monthly = technical.get("monthly_structure", {})
    divergence = technical.get("latest_rsi_divergence")
    divergence_text = divergence.get("kind") if isinstance(divergence, dict) else "yok"
    return (
        f"Teknik yapı {_num(technical.get('score'), 0)}/100 ile {str(technical.get('label', 'VERİ YETERSİZ')).casefold()}. Günlük piyasa yapısı "
        f"{structure.get('state', '—')} ve son teyitli olay {structure.get('event', structure.get('bos', '—'))}; haftalık "
        f"{weekly.get('state', '—')} / {weekly.get('event', '—')}, aylık {monthly.get('state', '—')} / {monthly.get('event', '—')}. "
        f"AlphaTrend {technical.get('alpha_trend_state', '—')}, RSI {_num(technical.get('rsi14'))}, SMI {_num(technical.get('smi'))}, "
        f"MACD histogram {_num(technical.get('macd_hist'), 3)}, OBV 10 günlük değişim {_pct(technical.get('obv_10d_change'))}; son RSI uyumsuzluğu {divergence_text}. "
        "İndikatörler piyasa yapısının yerine geçmiyor, yalnız yapıyı teyit veya zayıflatmak için kullanılıyor."
    )


def _levels_paragraph(report: ResearchReport) -> str:
    if report.supports:
        support = report.supports[0]
        support_text = (
            f"en yakın destek {support.low:.2f}–{support.high:.2f} bölgesi; kalite Q{support.score:.0f}, "
            f"fiyata uzaklık {support.distance_atr:.1f} ATR ve durum {support.status.casefold()}"
        )
    else:
        support_text = "fiyatın altında yeterli kalite ve yakınlık koşullarını sağlayan aktif destek bulunmuyor"
    if report.resistances:
        resistance = report.resistances[0]
        resistance_text = (
            f"en yakın direnç {resistance.low:.2f}–{resistance.high:.2f}; kalite Q{resistance.score:.0f}, "
            f"fiyata uzaklık {resistance.distance_atr:.1f} ATR ve durum {resistance.status.casefold()}"
        )
    else:
        resistance_text = "fiyatın üstünde yeterli kalite ve yakınlık koşullarını sağlayan aktif direnç bulunmuyor"
    return (
        f"Kritik seviyelerde {support_text}; {resistance_text}. Seviye yönü daima güncel fiyata göre kontrol ediliyor; fiyatın üstündeki bölge aktif destek, "
        "fiyatın altındaki bölge aktif direnç olarak gösterilmiyor. Kırılan bölgeler rol değişimiyle yeniden sınıflandırılıyor, uzak/eski seviyeler karar seviyesine taşınmıyor."
    )


def _risk_paragraph(report: ResearchReport) -> str:
    if report.main_risk is None:
        return (
            "Mevcut kanıt setinde 35/100 eşiğini aşan tek bir baskın risk başlığı oluşmuyor. Bu, risk olmadığı anlamına gelmiyor; "
            "yalnız veriyle doğrulanmış risklerin birbirinden belirgin şekilde ayrışmadığını gösteriyor. Eksik veri ayrıca risk gibi puanlanmıyor."
        )
    others = [item for item in report.risks if item.name != report.main_risk.name][:2]
    secondary = "; ".join(f"{item.name} {item.score:.0f}/100" for item in others)
    suffix = f" İkincil riskler: {secondary}." if secondary else ""
    return (
        f"Ana risk {report.main_risk.name} ve risk puanı {report.main_risk.score:.0f}/100. Dayanak: {report.main_risk.evidence} "
        "Risk sıralaması finansal kaldıraç, kâr kalitesi, değerleme hassasiyeti, teknik yapı ve likiditeyi aynı anda tarıyor; veri olmayan başlık nötr risk gibi uydurulmuyor."
        + suffix
    )


def _conclusion_paragraph(report: ResearchReport) -> str:
    scored = [item for item in report.dimensions if item.score is not None]
    strongest = max(scored, key=lambda item: item.score) if scored else None
    weakest = min(scored, key=lambda item: item.score) if scored else None
    strong_text = "belirgin güçlü boyut yok" if strongest is None else f"en güçlü taraf {strongest.name} ({strongest.score:.0f}/100)"
    weak_text = "belirgin zayıf boyut yok" if weakest is None else f"en zayıf taraf {weakest.name} ({weakest.score:.0f}/100)"
    risk_text = "baskın tek risk yok" if report.main_risk is None else f"ana risk {report.main_risk.name}"
    score_text = "—" if report.research_score is None else f"{report.research_score:.0f}/100"
    return (
        f"Genel araştırma skoru {score_text}; {strong_text}, {weak_text} ve {risk_text}. Sonuç tek bir göstergeye değil teknik yapı, bilanço, "
        "kâr kalitesi, borç/nakit, değerleme ve risk kanıtlarının birlikte okunmasına dayanıyor. Bu çıktı otomatik işlem çağrısı değil; hangi olumlu tezlerin hangi risk ve seviyelerle sınandığını gösteren karar desteğidir."
    )


def compose_research_commentary(report: ResearchReport) -> tuple[tuple[str, str], ...]:
    """Return titled analyst paragraphs in stable presentation order."""
    return (
        ("ŞİRKET NE DURUMDA?", _company_paragraph(report)),
        ("BİLANÇO İYİLEŞİYOR MU?", _balance_paragraph(report)),
        ("KÂR KALİTELİ Mİ?", _earnings_paragraph(report)),
        ("BORÇ VE NAKİT NE YÖNDE?", _debt_paragraph(report)),
        ("DEĞERLEME NASIL?", _valuation_paragraph(report)),
        ("TEKNİK YAPI NE DİYOR?", _technical_paragraph(report)),
        ("KRİTİK SEVİYELER NEREDE?", _levels_paragraph(report)),
        ("ASIL RİSK NE?", _risk_paragraph(report)),
        ("SONUÇ", _conclusion_paragraph(report)),
    )


def commentary_messages(report: ResearchReport, limit: int = 3900) -> tuple[str, ...]:
    """Format paragraphs into Telegram-safe messages without cutting a paragraph."""
    blocks = [f"📌 {title}\n{paragraph}" for title, paragraph in compose_research_commentary(report)]
    messages: list[str] = []
    current = f"🧾 {report.symbol} — ANALİST YORUMU"
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
            continue
        messages.append(current)
        current = block
    if current:
        messages.append(current)
    return tuple(messages)
