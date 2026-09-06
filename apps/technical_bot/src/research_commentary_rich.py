"""Institutional-style Turkish analyst commentary for the integrated research bundle.

The commentary interprets relationships between growth, margins, cash conversion,
leverage, valuation and peer position. Numbers are evidence, not the prose itself.
Missing evidence is stated explicitly instead of being converted to a conclusion.
"""

from __future__ import annotations

from typing import Any

from src import research_commentary as base
from src.research_engine import ResearchDimension, ResearchReport


def _dimension(report: ResearchReport, name: str) -> ResearchDimension | None:
    target = name.casefold()
    return next((item for item in report.dimensions if item.name.casefold() == target), None)


def _metric(report: ResearchReport, key: str) -> float | None:
    return base._finite(report.financial.get("metrics", {}).get(key))


def _valuation_metric(report: ResearchReport, key: str) -> tuple[float | None, float | None]:
    item = report.valuation.get("metrics", {}).get(key, {})
    if not isinstance(item, dict):
        return None, None
    return base._finite(item.get("value")), base._finite(item.get("percentile"))


def _fmt_money(value: Any) -> str:
    number = base._finite(value)
    if number is None:
        return "—"
    magnitude = abs(number)
    if magnitude >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.1f} mlr TL"
    if magnitude >= 1_000_000:
        return f"{number / 1_000_000:,.1f} mn TL"
    return f"{number:,.0f} TL"


def _growth_read(value: float | None, subject: str) -> str:
    if value is None:
        return f"{subject} büyümesi için yeterli veri yok"
    if value >= 30:
        return f"{subject} çok güçlü büyüyor"
    if value >= 10:
        return f"{subject} belirgin büyüyor"
    if value > -5:
        return f"{subject} yataya yakın"
    if value > -20:
        return f"{subject} daralıyor"
    return f"{subject} sert daralıyor"


def _margin_read(current: float | None, delta: float | None, label: str) -> str:
    if current is None:
        return f"{label} hesaplanamadı"
    if delta is None:
        return f"{label} %{current:.1f}; yıllık değişim verisi sınırlı"
    if delta >= 2:
        return f"{label} %{current:.1f} ve yıllık {delta:+.1f} puan genişliyor"
    if delta <= -2:
        return f"{label} %{current:.1f} ve yıllık {delta:+.1f} puan daralıyor"
    return f"{label} %{current:.1f}; yıllık değişim {delta:+.1f} puan ile sınırlı"


def _company_paragraph(report: ResearchReport) -> str:
    quality = _dimension(report, "Şirket Kalitesi")
    score_text = (
        "şirket kalitesi için puan üretilecek veri yok"
        if quality is None or quality.score is None
        else f"şirket kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}"
    )
    coverage = round(report.coverage * 100)
    if report.profile == "BANK":
        metrics = report.financial.get("metrics", {})
        assets_growth = base._finite(metrics.get("assets_growth"))
        equity_growth = base._finite(metrics.get("equity_growth"))
        roe = base._finite(metrics.get("roe"))
        loans_deposits = base._finite(metrics.get("loans_deposits"))
        return (
            f"{report.symbol} için {score_text}. Bankada değerlendirme sanayi şirketlerindeki cari oran veya "
            f"net borç/FAVÖK yerine aktif ve özkaynak büyümesi, kredi/mevduat dengesi, gelir-gider yapısı ve "
            f"özkaynak kârlılığı üzerinden kuruluyor. Aktif büyümesi {base._pct(assets_growth)}, özkaynak büyümesi "
            f"{base._pct(equity_growth)}, ROE {base._pct(roe)} ve kredi/mevduat {base._num(loans_deposits, 2)}x. "
            f"Bu kombinasyon özkaynak büyümesinin aktif büyümesini ne ölçüde taşıdığını ve bankanın büyürken "
            f"sermaye tamponunu koruyup korumadığını anlamaya yarıyor. Toplam araştırma kapsamı %{coverage}; "
            "resmî SYR/NPL gibi alınamayan veriler varsayılmıyor."
        )

    revenue_growth = _metric(report, "revenue_growth")
    net_growth = _metric(report, "net_income_growth")
    roe = _metric(report, "roe")
    roic = _metric(report, "roic")
    return (
        f"{report.symbol} için {score_text}. Resmin ilk önemli noktası, {_growth_read(revenue_growth, 'satışların')} "
        f"ve {_growth_read(net_growth, 'net kârın')}. ROE {base._pct(roe)}"
        + (f", ROIC {base._pct(roic)}" if roic is not None else "")
        + (
            ". Satış ve kâr aynı yönde büyüyorsa büyümenin kalitesi daha yüksek kabul edilir; kâr satıştan çok "
            "daha hızlı artıyorsa bunun marj genişlemesi mi, tek seferlik gelir mi yoksa finansman/vergi etkisi mi "
            "olduğu sonraki bölümlerde kontrol edilir. "
            f"Toplam araştırma veri kapsamı %{coverage}; eksik kalemler olumlu veya olumsuz varsayımla doldurulmaz."
        )
    )


def _operational_paragraph(report: ResearchReport) -> str:
    if report.profile == "BANK":
        metrics = report.financial.get("metrics", {})
        net_interest_growth = base._finite(metrics.get("net_interest_growth"))
        income_growth = base._finite(metrics.get("interest_income_growth"))
        expense_growth = base._finite(metrics.get("interest_expense_growth"))
        operating_expense = base._finite(metrics.get("operating_expense_growth"))
        roe = base._finite(metrics.get("roe"))
        spread_read = "faiz gelir-gider makası için veri yetersiz"
        if income_growth is not None and expense_growth is not None:
            diff = income_growth - expense_growth
            spread_read = (
                "faiz gelirleri faiz giderlerinden daha hızlı büyüyor; gelir makası destekleyici"
                if diff >= 5
                else "faiz giderleri gelir artışını yakalıyor; marj baskısı izlenmeli"
                if diff <= -5
                else "faiz gelir ve gider büyümesi birbirine yakın"
            )
        cost_read = "gider disiplini için veri yetersiz"
        if operating_expense is not None and net_interest_growth is not None:
            cost_read = (
                "faaliyet giderleri net faiz gelirinden yavaş artıyor; operasyonel kaldıraç olumlu"
                if operating_expense + 5 < net_interest_growth
                else "faaliyet giderleri gelir artışını zorluyor; maliyet disiplini kritik"
                if operating_expense > net_interest_growth + 5
                else "faaliyet giderleri gelir büyümesine yakın"
            )
        return (
            f"Bankanın operasyonel çekirdeğinde net faiz geliri büyümesi {base._pct(net_interest_growth)}. "
            f"{spread_read.capitalize()}; {cost_read}. ROE {base._pct(roe)} ile birlikte okunduğunda amaç yalnız "
            "kârın büyüyüp büyümediğini değil, büyümenin faiz makası ve maliyet kontrolüyle desteklenip "
            "desteklenmediğini görmek. Tek dönemlik güçlü kâr, gelir-gider makası bozuluyorsa kalıcı kalite "
            "olarak kabul edilmez."
        )

    revenue_growth = _metric(report, "revenue_growth")
    operating_growth = _metric(report, "operating_growth")
    gross_margin = _metric(report, "gross_margin")
    gross_delta = _metric(report, "gross_margin_yoy_change_pp")
    op_margin = _metric(report, "operating_margin")
    op_delta = _metric(report, "operating_margin_yoy_change_pp")
    ebitda_margin = _metric(report, "ebitda_margin")
    ebitda_q = _metric(report, "ebitda_margin_quarterly")
    roic = _metric(report, "roic")

    leverage_text = "operasyonel kaldıraç için veri yetersiz"
    if revenue_growth is not None and operating_growth is not None:
        spread = operating_growth - revenue_growth
        if spread >= 8:
            leverage_text = "faaliyet kârı satışlardan belirgin hızlı büyüyor; pozitif operasyonel kaldıraç var"
        elif spread <= -8:
            leverage_text = "faaliyet kârı satışların gerisinde; maliyet/marj baskısı büyümeyi zayıflatıyor"
        else:
            leverage_text = "faaliyet kârı satış büyümesine yakın ilerliyor"

    q_text = ""
    if ebitda_margin is not None and ebitda_q is not None:
        q_text = (
            f" Son çeyrek FAVÖK marjı %{ebitda_q:.1f}, TTM %{ebitda_margin:.1f}; "
            + (
                "son çeyrek marjı yıllık ortalamanın üzerinde ve son momentum destekleyici."
                if ebitda_q > ebitda_margin + 1
                else "son çeyrek marjı yıllık ortalamanın altında; yakın dönem kârlılık ivmesi zayıflamış olabilir."
                if ebitda_q < ebitda_margin - 1
                else "son çeyrek ile yıllık marj birbirine yakın."
            )
        )

    return (
        f"Operasyonel tarafta {_growth_read(revenue_growth, 'satışlar')}; faaliyet kârı büyümesi "
        f"{base._pct(operating_growth)} ve {leverage_text}. {_margin_read(gross_margin, gross_delta, 'Brüt marj')}; "
        f"{_margin_read(op_margin, op_delta, 'esas faaliyet marjı')}. "
        f"FAVÖK marjı {base._pct(ebitda_margin)} ve ROIC {base._pct(roic)}."
        + q_text
        + " Bu nedenle yalnız ciro büyümesi değil, büyümenin marja ve yatırılan sermaye getirisinin kalitesine "
        "dönüşüp dönüşmediği esas alınıyor."
    )


def _balance_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    label = str(financial.get("balance_label", "VERİ YETERSİZ")).casefold()
    score = base._finite(financial.get("balance_score"))
    score_text = "—" if score is None else f"{score:.0f}/100"

    if report.profile == "BANK":
        assets_growth = base._finite(metrics.get("assets_growth"))
        equity_growth = base._finite(metrics.get("equity_growth"))
        loans_deposits = base._finite(metrics.get("loans_deposits"))
        equity_assets = base._finite(metrics.get("equity_assets"))
        balance_read = "sermaye tamponu için veri sınırlı"
        if assets_growth is not None and equity_growth is not None:
            balance_read = (
                "özkaynak aktiflerden hızlı/benzer büyüyor; büyüme sermaye tarafından destekleniyor"
                if equity_growth >= assets_growth - 3
                else "aktif büyümesi özkaynağın önünde; sermaye yoğunluğu ayrıca izlenmeli"
            )
        return (
            f"Bilanço trendi {score_text} ile {label}. Aktif büyümesi {base._pct(assets_growth)}, özkaynak büyümesi "
            f"{base._pct(equity_growth)}, özkaynak/aktif {base._pct(equity_assets)} ve kredi/mevduat "
            f"{base._num(loans_deposits, 2)}x; {balance_read}. Bankalarda klasik cari oran kullanılmadığı için "
            "bilanço dayanıklılığı mevduat fonlaması ve özkaynak tamponu üzerinden okunuyor. Resmî sermaye "
            "yeterliliği (SYR) verisi yoksa bu oranlar yalnız vekil göstergedir."
        )

    current = base._finite(metrics.get("current_ratio"))
    quick = base._finite(metrics.get("quick_ratio"))
    cash = base._finite(metrics.get("cash_ratio"))
    liabilities_equity = base._finite(metrics.get("liabilities_equity"))
    financial_debt_ratio = base._finite(metrics.get("financial_debt_ratio"))

    if current is None:
        liquidity_read = "kısa vadeli likiditeyi güvenilir okumak için veri yetersiz"
    elif current < 1:
        liquidity_read = "dönen varlıklar kısa vadeli yükümlülükleri tam karşılamıyor; çalışma sermayesi baskısı var"
    elif current < 1.4:
        liquidity_read = "kısa vadeli likidite tamponu var ancak geniş değil"
    elif current <= 3:
        liquidity_read = "kısa vadeli yükümlülükler açısından likidite tamponu yeterli"
    else:
        liquidity_read = "likidite güçlü; fakat çok yüksek çalışma sermayesinin verimliliği de sorgulanmalı"

    return (
        f"Bilanço trendi {score_text} ile {label}. Cari oran {base._num(current, 2)}x, likidite oranı "
        f"{base._num(quick, 2)}x ve nakit oran {base._num(cash, 2)}x; {liquidity_read}. Toplam borç/özkaynak "
        f"{base._num(liabilities_equity, 2)}x, finansal borcun aktiflere oranı {base._pct(financial_debt_ratio)}. "
        "Burada amaç tek bir cari oran eşiğine bakmak değil; stoklara bağımlılık, nakit tamponu ve borcun "
        "özkaynak tabanına yükünü birlikte değerlendirmek."
    )


def _earnings_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    quality = _dimension(report, "Kâr Kalitesi")
    if report.profile == "BANK":
        if quality is None or quality.score is None:
            return (
                "Banka kâr kalitesinde yeterli veri kapsamı oluşmadığı için yapay puan üretilmiyor. Bankalarda "
                "sanayi şirketlerindeki CFO/net kâr yaklaşımı kullanılmıyor; net faiz geliri, ROE ve gider disiplini "
                "daha anlamlı kanıtlar."
            )
        return (
            f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. Net faiz geliri büyümesi "
            f"{base._pct(metrics.get('net_interest_growth'))}, ROE {base._pct(metrics.get('roe'))}, faaliyet gideri "
            f"büyümesi {base._pct(metrics.get('operating_expense_growth'))} ve net kâr büyümesi "
            f"{base._pct(metrics.get('net_income_growth'))}. Bu kombinasyon, kârın yalnız nominal olarak değil "
            "bankanın ana gelir motoru ve maliyet disipliniyle desteklenip desteklenmediğini gösterir."
        )

    if quality is None or quality.score is None:
        return (
            "Kâr kalitesi için nakit akımı ve işletme sermayesi kanıtı yeterli değil. Bu durumda yüksek görünen "
            "muhasebe kârı otomatik olarak kaliteli kabul edilmiyor; veri eksikliği olumlu varsayıma çevrilmiyor."
        )

    cfo_ni = base._finite(metrics.get("cfo_net_income"))
    fcf_margin = base._finite(metrics.get("fcf_margin"))
    accrual = base._finite(metrics.get("accrual_ratio"))
    rec_gap = base._finite(metrics.get("receivables_vs_sales_gap"))
    inv_gap = base._finite(metrics.get("inventory_vs_sales_gap"))

    cash_read = "nakde dönüşüm için veri yetersiz"
    if cfo_ni is not None:
        cash_read = (
            "faaliyet nakdi muhasebe kârını karşılıyor; kârın nakit desteği güçlü"
            if cfo_ni >= 1.0
            else "faaliyet nakdi net kârın altında; kârın nakde dönüşümü izlenmeli"
            if cfo_ni >= 0
            else "faaliyet nakdi negatif; raporlanan kâr ile nakit üretimi ayrışıyor"
        )
    working_read = "işletme sermayesi ayrışması için veri sınırlı"
    warnings = []
    if rec_gap is not None and rec_gap > 15:
        warnings.append("alacaklar satışlardan hızlı büyüyor")
    if inv_gap is not None and inv_gap > 20:
        warnings.append("stoklar satışlardan hızlı büyüyor")
    if warnings:
        working_read = "; ".join(warnings) + "; nakit dönüşümünde baskı yaratabilir"
    elif rec_gap is not None or inv_gap is not None:
        working_read = "alacak/stok büyümesi satışlardan belirgin kopmuyor"

    return (
        f"Kâr kalitesi {quality.score:.0f}/100 ile {quality.label.casefold()}. CFO/net kâr "
        f"{base._num(cfo_ni, 2)}x ve {cash_read}. FCF marjı {base._pct(fcf_margin)}, tahakkuk oranı "
        f"{base._pct(accrual)}; {working_read}. Böylece net kârın yalnız gelir tablosunda değil, faaliyet nakdi "
        "ve serbest nakit akışıyla doğrulanıp doğrulanmadığı kontrol ediliyor."
    )


def _debt_paragraph(report: ResearchReport) -> str:
    financial = report.financial
    metrics = financial.get("metrics", {})
    if report.profile == "BANK":
        return (
            "Bankalarda mevduat ve finansal yükümlülükler iş modelinin parçası olduğundan klasik net borç/FAVÖK "
            f"kullanılmıyor. Kredi/mevduat {base._num(metrics.get('loans_deposits'), 2)}x, özkaynak/aktif "
            f"{base._pct(metrics.get('equity_assets'))}. Bu oranlar fonlama dengesi ve sermaye tamponu için izlenir; "
            "resmî SYR veya likidite karşılama oranı gibi sunulmaz."
        )

    nd_ebitda = base._finite(metrics.get("net_debt_ebitda"))
    nde = base._finite(metrics.get("net_debt_equity"))
    change = base._finite(metrics.get("net_debt_yoy_change"))
    coverage = base._finite(metrics.get("interest_coverage"))
    fcf = base._finite(metrics.get("fcf_ttm"))

    if nd_ebitda is None:
        debt_read = "borcun FAVÖK karşısındaki taşınabilirliği için veri yetersiz"
    elif nd_ebitda <= 1:
        debt_read = "net borç/FAVÖK düşük; operasyonel nakit yaratımı borç yüküne karşı güçlü tampon sağlıyor"
    elif nd_ebitda <= 2.5:
        debt_read = "kaldıraç yönetilebilir aralıkta"
    elif nd_ebitda <= 4:
        debt_read = "kaldıraç yükselmiş; kâr ve nakit akışının devamlılığı daha kritik"
    else:
        debt_read = "net borç/FAVÖK yüksek; borç servis kapasitesi temel risklerden biri"

    interest_read = ""
    if coverage is not None:
        interest_read = (
            " Faiz karşılama rahat."
            if coverage >= 4
            else " Faiz giderine karşı tampon sınırlı."
            if coverage >= 1.5
            else " Faiz karşılama zayıf; finansman gideri kârı tehdit edebilir."
        )

    return (
        f"Borç yönü {str(financial.get('debt_direction', 'VERİ YETERSİZ')).casefold()}. Net borç/FAVÖK "
        f"{base._num(nd_ebitda, 2)}x, net borç/özkaynak {base._num(nde, 2)}x ve yıllık net borç değişimi "
        f"{base._pct(change)}; {debt_read}.{interest_read} Serbest nakit akışı {_fmt_money(fcf)}. Borcun nominal "
        "büyüklüğünden çok yönü, FAVÖK karşısındaki yükü ve nakit üretimiyle gerçekten azaltılabilir olup olmadığı "
        "esas alınıyor."
    )


def _valuation_paragraph(report: ResearchReport) -> str:
    dimension = _dimension(report, "Değerleme")
    valuation = report.valuation
    if dimension is None or dimension.score is None:
        return (
            "Değerleme tarafında yeterli karşılaştırılabilir veri oluşmadığı için ucuz/pahalı hükmü üretilmiyor. "
            "Negatif paydalı veya anlamsız çarpanlar sırf tablo dolsun diye puana alınmıyor."
        )

    pe, pe_pct = _valuation_metric(report, "pe")
    pb, pb_pct = _valuation_metric(report, "pb")
    ev_ebitda, ev_pct = _valuation_metric(report, "ev_ebitda")
    ev_sales, sales_pct = _valuation_metric(report, "ev_sales")
    peg, _ = _valuation_metric(report, "peg")
    p_fcf, _ = _valuation_metric(report, "p_fcf")
    earnings_yield, _ = _valuation_metric(report, "earnings_yield")

    def compare(name: str, value: float | None, percentile: float | None) -> str:
        if value is None:
            return f"{name} hesaplanamadı"
        if percentile is None:
            return f"{name} {value:.2f}x"
        if percentile <= 25:
            return f"{name} {value:.2f}x ile karşılaştırma evreninin düşük çarpanlı çeyreğinde"
        if percentile >= 75:
            return f"{name} {value:.2f}x ile karşılaştırma evreninin yüksek çarpanlı çeyreğinde"
        return f"{name} {value:.2f}x ile karşılaştırma evreninin orta bandında"

    if report.profile == "BANK":
        body = (
            f"{compare('F/K', pe, pe_pct)}; {compare('PD/DD', pb, pb_pct)}. Bankada bu çarpanlar ROE ve "
            "sermaye yapısıyla birlikte okunmalı: düşük PD/DD düşük kârlılığın sonucu da olabilir, yüksek PD/DD ise "
            "yüksek ve sürdürülebilir ROE ile gerekçelenebilir. FD/FAVÖK banka için karar metriği yapılmıyor."
        )
    elif report.profile == "GYO":
        body = (
            f"{compare('PD/DD', pb, pb_pct)}; {compare('F/K', pe, pe_pct)}. GYO'da gerçek portföy ekspertiz/NAD "
            "verisi olmadan PD/NAD hesaplanmadığı için düşük PD/DD otomatik iskonto olarak yorumlanmıyor; varlık "
            "kalitesi, borç ve kira/nakit üretimiyle birlikte okunmalı."
        )
    else:
        body = (
            f"{compare('F/K', pe, pe_pct)}; {compare('PD/DD', pb, pb_pct)}; "
            f"{compare('FD/FAVÖK', ev_ebitda, ev_pct)}; {compare('FD/Satış', ev_sales, sales_pct)}. "
            f"PEG {base._num(peg, 2)}x, Fiyat/FCF {base._num(p_fcf, 2)}x ve kazanç verimi "
            f"{base._pct(earnings_yield)}."
        )

    return (
        f"Değerleme boyutu {dimension.score:.0f}/100 ile {dimension.label.casefold()} ve evren "
        f"{valuation.get('scope', '—')}. {body} PEG burada ileriye dönük analist tahmini değil, mevcut F/K'nın "
        "son dört çeyrek net kâr büyümesine oranıdır; büyüme negatifse gösterilmez. Sonuç olarak düşük çarpan ancak "
        "kârlılık ve nakit kalitesi bozulmuyorsa gerçek iskonto adayıdır; aksi halde değer tuzağı olabilir."
    )


def _peer_paragraph(report: ResearchReport) -> str:
    peer = report.valuation.get("peer_analysis", {})
    scope = str(peer.get("scope") or report.valuation.get("scope") or "Karşılaştırma yok")
    peers = list(peer.get("peers", ()))
    benchmarks = peer.get("benchmarks", {})
    if not peers and not benchmarks:
        return (
            "Sektör/rakip tablosu için yeterli karşılaştırılabilir veri alınamadı. Böyle bir durumda şirketin "
            "çarpanını BIST geneline zorla kıyaslayıp kesin sektör sonucu üretmek yerine karşılaştırma kapsamı açıkça "
            "eksik bırakılıyor."
        )

    observations = []
    for key, label in (("pe", "F/K"), ("pb", "PD/DD"), ("ev_ebitda", "FD/FAVÖK"), ("roe", "ROE")):
        item = benchmarks.get(key, {})
        if not isinstance(item, dict):
            continue
        target = base._finite(item.get("target"))
        median = base._finite(item.get("median"))
        if target is None or median is None:
            continue
        if key == "roe":
            phrase = "medyanın üzerinde" if target > median else "medyanın altında" if target < median else "medyana yakın"
        else:
            phrase = "medyanın altında" if target < median else "medyanın üzerinde" if target > median else "medyana yakın"
        observations.append(f"{label} {phrase} ({target:.2f} vs {median:.2f})")
    evidence = "; ".join(observations[:4]) or "ana çarpanlarda medyan karşılaştırması sınırlı"
    names = ", ".join(str(item.get("symbol", "")) for item in peers[:6] if item.get("symbol"))
    peer_text = f"Karşılaştırma kümesinde öne çıkan semboller: {names}." if names else ""

    return (
        f"Rakip analizi {scope} üzerinden kuruluyor; {evidence}. {peer_text} Buradaki amaç en düşük çarpanlı hisseyi "
        "seçmek değil, fiyatlama ile iş kalitesinin aynı anda nerede durduğunu görmek. Örneğin sektör altı F/K ile "
        "birlikte sektör altı ROE görülüyorsa iskonto kısmen haklı olabilir; düşük çarpan güçlü ROE/marj/nakit "
        "üretimiyle birlikteyse göreli değerleme daha anlamlı hale gelir."
    )


def _forensic_paragraph(report: ResearchReport) -> str:
    scores = report.financial.get("forensic_scores", {})
    if report.profile == "BANK":
        beta = scores.get("beta", {})
        value = beta.get("value") if isinstance(beta, dict) else None
        return (
            "Altman Z, Beneish M, Graham ve klasik Piotroski F-Skor endüstriyel şirket finansalları için tasarlandığı "
            "için bankaya mekanik biçimde uygulanmadı. Bu, 'veri yok' değil yöntemsel bir tercihtir. "
            f"BIST 100'e göre 1 yıllık günlük beta {base._num(value, 2)}; beta yalnız fiyat duyarlılığını gösterir, "
            "banka bilanço kalitesinin yerine geçmez."
        )

    altman = scores.get("altman_z", {})
    beneish = scores.get("beneish_m", {})
    graham = scores.get("graham_number", {})
    piotroski = scores.get("piotroski_f", {})
    beta = scores.get("beta", {})

    altman_text = (
        "Altman Z için veri yetersiz"
        if not isinstance(altman, dict) or altman.get("value") is None
        else f"Altman Z {float(altman['value']):.3f} ({altman.get('label', '—')})"
    )
    beneish_text = (
        "Beneish M tam 8 bileşenle hesaplanamadı"
        if not isinstance(beneish, dict) or beneish.get("value") is None
        else f"Beneish M {float(beneish['value']):.3f} ({beneish.get('label', '—')})"
    )
    graham_text = (
        "Graham sayısı hesaplanamadı"
        if not isinstance(graham, dict) or graham.get("value") is None
        else f"Graham sayısı {float(graham['value']):.2f}"
    )
    if isinstance(piotroski, dict) and piotroski.get("score") is not None:
        pio_text = f"Piotroski {piotroski.get('score')}/{piotroski.get('max_score')}"
        if piotroski.get("official_score") is None:
            pio_text += " (kısmi gözlem)"
        else:
            pio_text += " (tam 9 ölçüt)"
    else:
        pio_text = "Piotroski için veri yetersiz"
    beta_text = (
        "beta hesaplanamadı"
        if not isinstance(beta, dict) or beta.get("value") is None
        else f"beta {float(beta['value']):.2f}"
    )

    return (
        f"Finansal sağlık/forensic göstergelerinde {altman_text}; {beneish_text}; {graham_text}; {pio_text}; "
        f"{beta_text}. Bu skorların hiçbiri tek başına şirket kalitesi hükmü değildir. Altman finansal baskı "
        "olasılığına, Beneish raporlama anomalilerine, Piotroski temel güçlenme ölçütlerine, Graham bilanço-kâr "
        "temelli kaba değer referansına ve beta piyasa duyarlılığına bakar. Eksik Beneish/Piotroski bileşeni sıfır "
        "puan sayılmadığı için skorlar veri kapsamıyla birlikte okunur."
    )


def _zone(value: float | None, *, upper: float, lower: float, high: str, low: str) -> str:
    if value is None:
        return "veri yetersiz"
    if value >= upper:
        return high
    if value <= lower:
        return low
    return "nötr bölge"


def _direction(value: float | None, signal: float | None) -> str:
    if value is None or signal is None:
        return "sinyal karşılaştırması için veri yetersiz"
    if value > signal:
        return "sinyal çizgisinin üzerinde"
    if value < signal:
        return "sinyal çizgisinin altında"
    return "sinyal çizgisiyle aynı seviyede"


def _technical_paragraph_rich(report: ResearchReport) -> str:
    technical = report.technical
    structure = technical.get("structure", {})
    weekly = technical.get("weekly_structure", {})
    monthly = technical.get("monthly_structure", {})
    elliott = technical.get("elliott", {})

    score = base._finite(technical.get("score"))
    score_text = "—" if score is None else f"{score:.0f}/100"
    label = str(technical.get("label", "VERİ YETERSİZ")).casefold()

    rsi = base._finite(technical.get("rsi14"))
    smi = base._finite(technical.get("smi"))
    smi_signal = base._finite(technical.get("smi_signal"))
    macd_hist = base._finite(technical.get("macd_hist"))
    obv_change = base._finite(technical.get("obv_10d_change"))
    rvol = base._finite(technical.get("rvol20"))
    atr_pct = base._finite(technical.get("atr_pct"))
    divergence = technical.get("latest_rsi_divergence")
    divergence_text = divergence.get("kind") if isinstance(divergence, dict) else "yok"

    rsi_zone = _zone(rsi, upper=70.0, lower=30.0, high="aşırı alım bölgesi", low="aşırı satım bölgesi")
    smi_zone = _zone(
        smi,
        upper=40.0,
        lower=-40.0,
        high="+40 üzeri aşırı alım bölgesi",
        low="-40 altı aşırı satım bölgesi",
    )
    macd_state = (
        "veri yetersiz"
        if macd_hist is None
        else "pozitif histogram"
        if macd_hist > 0
        else "negatif histogram"
        if macd_hist < 0
        else "sıfır histogram"
    )
    volume_state = (
        "RVOL verisi yetersiz"
        if rvol is None
        else f"RVOL20 {rvol:.2f}x ile olağanın üzerinde hacim"
        if rvol >= 1.5
        else f"RVOL20 {rvol:.2f}x ile normal hacim"
        if rvol >= 0.8
        else f"RVOL20 {rvol:.2f}x ile zayıf hacim"
    )
    volatility_state = (
        "ATR verisi yetersiz"
        if atr_pct is None
        else f"ATR %{atr_pct:.1f} ile yüksek volatilite"
        if atr_pct >= 5.0
        else f"ATR %{atr_pct:.1f} ile orta volatilite"
        if atr_pct >= 2.5
        else f"ATR %{atr_pct:.1f} ile görece düşük volatilite"
    )
    obv_text = "—" if obv_change is None else f"%{obv_change:+.1f}"

    daily_state = str(structure.get("state", "—"))
    weekly_state = str(weekly.get("state", "—"))
    alignment = "zaman dilimleri arasında net hizalanma yok"
    bullish = sum("HH / HL" in state for state in (daily_state, weekly_state))
    bearish = sum("LH / LL" in state for state in (daily_state, weekly_state))
    if bullish == 2:
        alignment = "günlük ve haftalık yükseliş yapısı aynı yönde; yapı teyidi daha güçlü"
    elif bearish == 2:
        alignment = "günlük ve haftalık düşüş yapısı aynı yönde; yapısal baskı daha güçlü"
    elif bullish and bearish:
        alignment = "günlük ve haftalık yapı ters yönde; kısa vadeli hareket üst zaman dilimince teyit edilmiyor"

    invalidation = base._finite(elliott.get("invalidation"))
    invalidation_text = "—" if invalidation is None else f"{invalidation:,.2f}"
    confidence = base._finite(elliott.get("confidence"))
    confidence_text = "—" if confidence is None else f"%{confidence:.0f}"

    return (
        f"Teknik yapı {score_text} ile {label}. Günlük piyasa yapısı {daily_state} ve "
        f"{structure.get('event', structure.get('bos', '—'))}; haftalık {weekly_state} / "
        f"{weekly.get('event', '—')}, aylık {monthly.get('state', '—')} / {monthly.get('event', '—')}. "
        f"{alignment.capitalize()}. AlphaTrend {technical.get('alpha_trend_state', '—')}; Bollinger konumu "
        f"{technical.get('bollinger_state', '—')}. Momentumda RSI {base._num(rsi)} ile {rsi_zone}, son regular "
        f"uyumsuzluk {divergence_text}; SMI {base._num(smi)} ({smi_zone}, {_direction(smi, smi_signal)}), "
        f"MACD {macd_state}, OBV 10 günlük değişim {obv_text}. Hacim/volatilite tarafında {volume_state} ve "
        f"{volatility_state}. Elliott bağlamı {elliott.get('primary', '—')}; alternatif "
        f"{elliott.get('alternate', '—')}, güven {confidence_text}, invalidation {invalidation_text}. Bu kanıtlar "
        "AL/SAT çağrısı üretmek için değil, HH/HL/LH/LL, BOS/CHoCH ve aktif seviye yapısının birbirini teyit edip "
        "etmediğini ölçmek için kullanılıyor."
    )


def _levels_paragraph(report: ResearchReport) -> str:
    return base._levels_paragraph(report)


def _risk_paragraph(report: ResearchReport) -> str:
    if report.main_risk is None:
        return (
            "Mevcut kanıtlar tek bir baskın riski diğerlerinden belirgin ayırmıyor. Bu, risk olmadığı anlamına "
            "gelmez; yalnız ölçülen kaldıraç, kâr kalitesi, değerleme, teknik yapı ve likidite başlıklarının "
            "hiçbirinin tek başına baskınlaşmadığını gösterir. Eksik veri risk puanı gibi uydurulmaz."
        )
    others = [item for item in report.risks if item.name != report.main_risk.name][:3]
    secondary = "; ".join(f"{item.name} {item.score:.0f}/100" for item in others)
    suffix = f" İkincil riskler: {secondary}." if secondary else ""
    return (
        f"Şu anda en yüksek ölçülen risk {report.main_risk.name} ({report.main_risk.score:.0f}/100). "
        f"Dayanak: {report.main_risk.evidence} Bu riskin önemi, tek bir oranın yüksekliğinden değil diğer "
        "kanıtlarla aynı yönde olup olmamasından gelir; örneğin yüksek kaldıraç aynı anda zayıf FCF ve düşen marjla "
        "birleşirse risk daha ciddidir."
        + suffix
    )


def _conclusion_paragraph(report: ResearchReport) -> str:
    scored = [item for item in report.dimensions if item.score is not None]
    strongest = max(scored, key=lambda item: item.score) if scored else None
    weakest = min(scored, key=lambda item: item.score) if scored else None
    strong_text = "ölçülebilir güçlü boyut yok" if strongest is None else f"en güçlü boyut {strongest.name} ({strongest.score:.0f}/100)"
    weak_text = "ölçülebilir zayıf boyut yok" if weakest is None else f"en zayıf boyut {weakest.name} ({weakest.score:.0f}/100)"
    risk_text = "baskın tek risk ayrışmıyor" if report.main_risk is None else f"ana risk {report.main_risk.name} ({report.main_risk.score:.0f}/100)"
    balance = str(report.financial.get("balance_label", "—")).casefold()
    quality = str(report.financial.get("earnings_quality_label", "—")).casefold()
    debt = str(report.financial.get("debt_direction", "—")).casefold()
    technical = str(report.technical.get("label", "—")).casefold()
    return (
        f"Toplu resimde {strong_text}; {weak_text} ve {risk_text}. Bilanço trendi {balance}, kâr kalitesi {quality}, "
        f"borç yönü {debt}, teknik görünüm {technical}. Bundan sonraki teyit için üç şey özellikle izlenmeli: "
        "marjların ve nakit dönüşümünün son çeyreklerde aynı yönde kalması, borcun faaliyet kârından hızlı büyümemesi "
        "ve fiyatın aktif destek/direnç yaşam döngüsünde üst zaman dilimleriyle uyumlu hareket etmesi. Araştırma "
        "çıktısı yatırım tavsiyesi veya otomatik işlem sinyali değil; şirket kalitesi, fiyatlama ve riskin aynı "
        "çerçevede okunması için karar destek özetidir."
    )


def compose_research_commentary(report: ResearchReport) -> tuple[tuple[str, str], ...]:
    """Return interpretation-first analyst sections in user-facing order."""
    return (
        ("ŞİRKET NE DURUMDA?", _company_paragraph(report)),
        ("OPERASYONEL KALİTE VE KÂRLILIK", _operational_paragraph(report)),
        ("BİLANÇO VE LİKİDİTE", _balance_paragraph(report)),
        ("KÂR KALİTELİ Mİ?", _earnings_paragraph(report)),
        ("BORÇ VE NAKİT NE YÖNDE?", _debt_paragraph(report)),
        ("DEĞERLEME NASIL?", _valuation_paragraph(report)),
        ("SEKTÖR VE RAKİPLER", _peer_paragraph(report)),
        ("FİNANSAL SKORLAR NE SÖYLÜYOR?", _forensic_paragraph(report)),
        ("TEKNİK YAPI NE DİYOR?", _technical_paragraph_rich(report)),
        ("KRİTİK SEVİYELER NEREDE?", _levels_paragraph(report)),
        ("ASIL RİSK NE?", _risk_paragraph(report)),
        ("SONUÇ", _conclusion_paragraph(report)),
    )


def commentary_messages(report: ResearchReport, limit: int = 3900) -> tuple[str, ...]:
    """Split ordered analyst sections only at section boundaries."""
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
