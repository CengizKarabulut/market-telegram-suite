"""Extended financial diagnostics, forensic scores and peer intelligence.

The module deliberately derives ratios from reported financial statements when
possible. Missing rows reduce coverage; no missing field is silently converted
to zero. Bank profiles skip industrial-company ratios/scores whose economics do
not apply.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src import research_engine as core
from src.fundamental_analysis import FundamentalReport

EXTRA_ALIASES: dict[str, tuple[str, ...]] = {
    "liabilities": (
        "toplam yukumlulukler",
        "toplam borclar",
        "total liabilities",
        "liabilities total",
    ),
    "noncurrent_assets": (
        "duran varliklar",
        "non current assets",
        "non-current assets",
    ),
    "ppe": (
        "maddi duran varliklar",
        "property plant and equipment",
        "property plant equipment",
    ),
    "retained_earnings": (
        "gecmis yillar karlari zararlari",
        "gecmis yillar karlari",
        "retained earnings",
        "accumulated profits losses",
    ),
    "paid_in_capital": (
        "odenmis sermaye",
        "issued capital",
        "paid in capital",
        "share capital",
    ),
    "depreciation": (
        "amortisman giderleri",
        "amortisman ve itfa paylari",
        "depreciation and amortization",
        "depreciation amortization",
    ),
    "sga": (
        "genel yonetim giderleri",
        "pazarlama giderleri",
        "selling general administrative expenses",
        "selling general and administrative expenses",
    ),
    "tax_expense": (
        "vergi gideri geliri",
        "donem vergi gideri",
        "tax expense income",
        "income tax expense",
    ),
}

RATIO_GROUPS: tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...] = (
    (
        "Likidite Oranları",
        (
            ("current_ratio", "Cari Oran", "x"),
            ("quick_ratio", "Likidite Oranı", "x"),
            ("cash_ratio", "Nakit Oran", "x"),
        ),
    ),
    (
        "Kaldıraç Oranları",
        (
            ("financial_debt_ratio", "Finansal Borç Oranı", "%"),
            ("leverage_ratio", "Kaldıraç Oranı", "x"),
            ("liabilities_equity", "Toplam Borç / Özkaynak", "x"),
            ("net_debt_ebitda", "Net Borç / FAVÖK", "x"),
            ("interest_coverage", "Faiz Karşılama", "x"),
        ),
    ),
    (
        "Faaliyet Etkinlik Oranları",
        (
            ("asset_turnover", "Aktif Devir Hızı", "x"),
            ("inventory_turnover", "Stok Devir Hızı", "x"),
            ("payables_turnover", "Borç Devir Hızı", "x"),
            ("equity_turnover", "Özkaynak Devir Hızı", "x"),
            ("receivables_turnover", "Alacak Devir Hızı", "x"),
        ),
    ),
    (
        "Kârlılık Oranları",
        (
            ("roa", "Aktif Kârlılık", "%"),
            ("gross_margin", "Brüt Kâr Marjı", "%"),
            ("gross_margin_quarterly", "Brüt Kâr Marjı (Çeyreklik)", "%"),
            ("ebitda_margin", "FAVÖK Marjı", "%"),
            ("ebitda_margin_quarterly", "FAVÖK Marjı (Çeyreklik)", "%"),
            ("operating_margin", "Esas Faaliyet Kâr Marjı", "%"),
            ("operating_margin_quarterly", "Esas Faaliyet Kâr Marjı (Çeyreklik)", "%"),
            ("net_margin", "Net Kâr Marjı", "%"),
            ("net_margin_quarterly", "Net Kâr Marjı (Çeyreklik)", "%"),
            ("roe", "Özkaynak Kârlılığı", "%"),
            ("roic", "ROIC", "%"),
            ("eps", "Hisse Başına Kâr", "₺"),
        ),
    ),
)


def _finite(value: Any) -> float | None:
    return core._finite(value)


def _series(frame: pd.DataFrame | None, key: str) -> pd.Series | None:
    """Read a financial row using core aliases first, then extended aliases."""
    if key in core.STATEMENT_ALIASES:
        return core._statement_series(frame, key)
    if frame is None or frame.empty:
        return None
    aliases = EXTRA_ALIASES.get(key, ())
    if not aliases:
        return None
    labels = [(core._norm(index), index) for index in frame.index]
    matches: list[Any] = []
    for alias in aliases:
        target = core._norm(alias)
        exact = [index for label, index in labels if label == target]
        if exact:
            matches = exact
            break
    if not matches:
        candidates: list[tuple[int, Any]] = []
        for alias in aliases:
            target = core._norm(alias)
            for label, index in labels:
                if target and target in label:
                    candidates.append((len(label), index))
        if candidates:
            matches = [sorted(candidates, key=lambda item: item[0])[0][1]]
    if not matches:
        return None
    selected = frame.loc[matches[0]]
    rows = selected if isinstance(selected, pd.DataFrame) else pd.DataFrame([selected])
    rows = rows.apply(pd.to_numeric, errors="coerce")
    row = max((item for _, item in rows.iterrows()), key=lambda item: int(item.notna().sum()), default=None)
    if row is None:
        return None
    ordered = sorted(row.index, key=core._period_key)
    return row.reindex(ordered)


def _vals(frame: pd.DataFrame | None, key: str) -> list[float | None]:
    return core._values(_series(frame, key))


def _latest(values: list[float | None], lag: int = 0) -> float | None:
    return core._latest(values, lag)


def _sum4(values: list[float | None], offset: int = 0) -> float | None:
    return core._sum4(values, offset)


def _ratio(num: float | None, den: float | None, scale: float = 1.0) -> float | None:
    return core._ratio(num, den, scale)


def _avg(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return (current + previous) / 2.0


def _positive(value: float | None) -> bool | None:
    if value is None:
        return None
    return value > 0


def _market_snapshot(symbol: str, price: float | None) -> dict[str, float | None]:
    """Best-effort current market values; statement ratios still work without them."""
    try:
        import borsapy as bp

        stock = bp.Ticker(symbol)
        try:
            fast = dict(stock.fast_info or {})
        except Exception:  # noqa: BLE001
            fast = {}
        try:
            info = dict(stock.info or {})
        except Exception:  # noqa: BLE001
            info = {}
    except Exception:  # noqa: BLE001
        return {"market_cap": None, "enterprise_value": None, "shares_outstanding": None}

    def pick(mapping: dict[str, Any], *names: str) -> float | None:
        normal = {core._norm(key): value for key, value in mapping.items()}
        for name in names:
            value = _finite(mapping.get(name))
            if value is None:
                value = _finite(normal.get(core._norm(name)))
            if value is not None and value > 0:
                return value
        return None

    market_cap = pick(fast, "market_cap", "marketCap", "market capitalization")
    if market_cap is None:
        market_cap = pick(info, "marketCap", "market_cap", "market capitalization")
    enterprise = pick(info, "enterpriseValue", "enterprise_value")
    shares = pick(info, "sharesOutstanding", "shares_outstanding", "impliedSharesOutstanding")
    if shares is None:
        shares = pick(fast, "shares", "shares_outstanding")
    if shares is None and market_cap is not None and price is not None and price > 0:
        shares = market_cap / price
    return {"market_cap": market_cap, "enterprise_value": enterprise, "shares_outstanding": shares}


def _beta(symbol: str) -> float | None:
    """1-year daily beta versus BIST 100; unavailable rather than fabricated."""
    try:
        import borsapy as bp

        stock = bp.Ticker(symbol).history(period="1y", interval="1d")
        if stock is None or stock.empty:
            return None
        stock_close = pd.to_numeric(stock["Close" if "Close" in stock.columns else "close"], errors="coerce")
        benchmark = None
        for benchmark_symbol in ("XU100", "BIST100"):
            try:
                candidate = bp.Ticker(benchmark_symbol).history(period="1y", interval="1d")
            except Exception:  # noqa: BLE001
                continue
            if candidate is not None and not candidate.empty:
                benchmark = candidate
                break
        if benchmark is None:
            return None
        benchmark_close = pd.to_numeric(
            benchmark["Close" if "Close" in benchmark.columns else "close"], errors="coerce"
        )
        joined = pd.concat(
            [stock_close.pct_change().rename("stock"), benchmark_close.pct_change().rename("market")], axis=1
        ).dropna()
        if len(joined) < 80:
            return None
        variance = float(joined["market"].var())
        if variance <= 0:
            return None
        return float(joined["stock"].cov(joined["market"]) / variance)
    except Exception:  # noqa: BLE001
        return None


def _piotroski(
    *,
    roa: float | None,
    roa_prev: float | None,
    cfo: float | None,
    net_income: float | None,
    leverage: float | None,
    leverage_prev: float | None,
    current_ratio: float | None,
    current_ratio_prev: float | None,
    paid_capital: float | None,
    paid_capital_prev: float | None,
    gross_margin: float | None,
    gross_margin_prev: float | None,
    asset_turnover: float | None,
    asset_turnover_prev: float | None,
) -> dict[str, Any]:
    criteria: dict[str, bool | None] = {
        "positive_roa": _positive(roa),
        "positive_cfo": _positive(cfo),
        "roa_improving": None if roa is None or roa_prev is None else roa > roa_prev,
        "cash_exceeds_profit": None if cfo is None or net_income is None else cfo > net_income,
        "leverage_improving": None if leverage is None or leverage_prev is None else leverage < leverage_prev,
        "liquidity_improving": None
        if current_ratio is None or current_ratio_prev is None
        else current_ratio > current_ratio_prev,
        "no_dilution_proxy": None
        if paid_capital is None or paid_capital_prev is None
        else paid_capital <= paid_capital_prev * 1.001,
        "gross_margin_improving": None
        if gross_margin is None or gross_margin_prev is None
        else gross_margin > gross_margin_prev,
        "asset_turnover_improving": None
        if asset_turnover is None or asset_turnover_prev is None
        else asset_turnover > asset_turnover_prev,
    }
    available = [value for value in criteria.values() if value is not None]
    score = sum(bool(value) for value in available)
    return {
        "score": score if available else None,
        "max_score": len(available),
        "coverage": round(len(available) / 9.0, 2),
        "official_score": score if len(available) == 9 else None,
        "criteria": criteria,
        "note": (
            "Ödenmiş sermaye değişimi hisse adedi değişimine vekil olarak kullanılır; "
            "9 ölçütün tamamı yoksa skor 'gözlenen/max' biçiminde gösterilir."
        ),
    }


def _altman(
    *,
    assets: float | None,
    liabilities: float | None,
    working_capital: float | None,
    retained_earnings: float | None,
    ebit: float | None,
    market_cap: float | None,
    revenue: float | None,
) -> dict[str, Any]:
    parts = (assets, liabilities, working_capital, retained_earnings, ebit, market_cap, revenue)
    coverage = sum(value is not None for value in parts) / len(parts)
    if (
        assets is None
        or assets <= 0
        or liabilities is None
        or liabilities <= 0
        or working_capital is None
        or retained_earnings is None
        or ebit is None
        or market_cap is None
        or revenue is None
    ):
        return {"value": None, "coverage": round(coverage, 2), "label": "Veri yetersiz"}
    value = (
        1.2 * working_capital / assets
        + 1.4 * retained_earnings / assets
        + 3.3 * ebit / assets
        + 0.6 * market_cap / liabilities
        + 1.0 * revenue / assets
    )
    label = "Görece güçlü" if value > 2.99 else "Gri bölge" if value >= 1.81 else "Finansal baskı"
    return {"value": round(value, 3), "coverage": 1.0, "label": label}


def _beneish(
    *,
    revenue: float | None,
    revenue_prev: float | None,
    receivables: float | None,
    receivables_prev: float | None,
    gross_profit: float | None,
    gross_profit_prev: float | None,
    current_assets: float | None,
    current_assets_prev: float | None,
    ppe: float | None,
    ppe_prev: float | None,
    assets: float | None,
    assets_prev: float | None,
    depreciation: float | None,
    depreciation_prev: float | None,
    sga: float | None,
    sga_prev: float | None,
    liabilities: float | None,
    liabilities_prev: float | None,
    net_income: float | None,
    cfo: float | None,
) -> dict[str, Any]:
    def div(a: float | None, b: float | None) -> float | None:
        return _ratio(a, b)

    dsri = div(div(receivables, revenue), div(receivables_prev, revenue_prev))
    gross_margin = None if revenue is None or gross_profit is None else gross_profit / revenue
    gross_margin_prev = None if revenue_prev is None or gross_profit_prev is None else gross_profit_prev / revenue_prev
    gmi = div(gross_margin_prev, gross_margin)
    aqi_current = None if assets is None or current_assets is None or ppe is None or assets == 0 else 1.0 - (current_assets + ppe) / assets
    aqi_prev = None if assets_prev is None or current_assets_prev is None or ppe_prev is None or assets_prev == 0 else 1.0 - (current_assets_prev + ppe_prev) / assets_prev
    aqi = div(aqi_current, aqi_prev)
    sgi = div(revenue, revenue_prev)
    dep_rate = div(depreciation, None if depreciation is None or ppe is None else depreciation + ppe)
    dep_rate_prev = div(depreciation_prev, None if depreciation_prev is None or ppe_prev is None else depreciation_prev + ppe_prev)
    depi = div(dep_rate_prev, dep_rate)
    sgai = div(div(sga, revenue), div(sga_prev, revenue_prev))
    lvgi = div(div(liabilities, assets), div(liabilities_prev, assets_prev))
    tata = None if net_income is None or cfo is None or assets is None or assets == 0 else (net_income - cfo) / assets
    components = {"DSRI": dsri, "GMI": gmi, "AQI": aqi, "SGI": sgi, "DEPI": depi, "SGAI": sgai, "TATA": tata, "LVGI": lvgi}
    available = [value for value in components.values() if value is not None and math.isfinite(value)]
    coverage = len(available) / 8.0
    if len(available) < 8:
        return {
            "value": None,
            "coverage": round(coverage, 2),
            "label": "Kısmi veri" if len(available) >= 6 else "Veri yetersiz",
            "components": components,
        }
    value = (
        -4.84
        + 0.920 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )
    label = "Düşük manipülasyon sinyali" if value < -1.78 else "Yakın izleme"
    return {"value": round(float(value), 3), "coverage": 1.0, "label": label, "components": components}


def enrich_financial_analysis(
    base: dict[str, Any],
    fundamental: FundamentalReport,
    balance: pd.DataFrame,
    income: pd.DataFrame,
    cashflow: pd.DataFrame | None,
) -> dict[str, Any]:
    """Add statement-derived ratios and forensic diagnostics to base analysis."""
    enriched = dict(base)
    metrics = dict(base.get("metrics", {}))
    if fundamental.profile == "BANK":
        metrics["beta"] = _beta(fundamental.symbol)
        enriched["metrics"] = metrics
        enriched["ratio_groups"] = ()
        enriched["forensic_scores"] = {
            "altman_z": {"value": None, "coverage": 0.0, "label": "Bankalarda uygulanmaz"},
            "beneish_m": {"value": None, "coverage": 0.0, "label": "Bankalarda uygulanmaz"},
            "graham_number": {"value": None, "coverage": 0.0, "label": "Bankalarda sınırlı anlam"},
            "piotroski_f": {
                "score": None,
                "max_score": 0,
                "coverage": 0.0,
                "official_score": None,
                "criteria": {},
                "note": "Klasik Piotroski endüstriyel şirket formatı bankalara uygulanmadı.",
            },
            "beta": {"value": metrics.get("beta"), "coverage": 1.0 if metrics.get("beta") is not None else 0.0},
        }
        return enriched

    b = {key: _vals(balance, key) for key in (
        "assets", "current_assets", "current_liabilities", "equity", "cash", "inventory", "receivables", "payables",
        "short_debt", "current_long_debt", "long_debt", "liabilities", "ppe", "retained_earnings", "paid_in_capital",
    )}
    i = {key: _vals(income, key) for key in (
        "revenue", "gross_profit", "operating_profit", "ebitda", "net_income", "finance_expense", "depreciation", "sga", "tax_expense",
    )}
    c = {key: _vals(cashflow, key) for key in ("cfo", "capex")} if cashflow is not None else {"cfo": [], "capex": []}

    assets = _latest(b["assets"])
    assets_prev = _latest(b["assets"], 4)
    current_assets = _latest(b["current_assets"])
    current_assets_prev = _latest(b["current_assets"], 4)
    current_liabilities = _latest(b["current_liabilities"])
    current_liabilities_prev = _latest(b["current_liabilities"], 4)
    equity = _latest(b["equity"])
    equity_prev = _latest(b["equity"], 4)
    cash = _latest(b["cash"])
    inventory = _latest(b["inventory"])
    inventory_prev = _latest(b["inventory"], 4)
    receivables = _latest(b["receivables"])
    receivables_prev = _latest(b["receivables"], 4)
    payables = _latest(b["payables"])
    payables_prev = _latest(b["payables"], 4)
    liabilities = _latest(b["liabilities"])
    liabilities_prev = _latest(b["liabilities"], 4)
    if liabilities is None and assets is not None and equity is not None:
        liabilities = assets - equity
    if liabilities_prev is None and assets_prev is not None and equity_prev is not None:
        liabilities_prev = assets_prev - equity_prev

    debt_parts = (_latest(b["short_debt"]), _latest(b["current_long_debt"]), _latest(b["long_debt"]))
    debt = sum(value or 0.0 for value in debt_parts) if any(value is not None for value in debt_parts) else None
    debt_prev_parts = (_latest(b["short_debt"], 4), _latest(b["current_long_debt"], 4), _latest(b["long_debt"], 4))
    debt_prev = sum(value or 0.0 for value in debt_prev_parts) if any(value is not None for value in debt_prev_parts) else None

    revenue_ttm, revenue_prev = _sum4(i["revenue"]), _sum4(i["revenue"], 4)
    gross_ttm, gross_prev = _sum4(i["gross_profit"]), _sum4(i["gross_profit"], 4)
    ebit_ttm = _sum4(i["operating_profit"])
    ebitda_ttm = _sum4(i["ebitda"])
    net_ttm, net_prev = _sum4(i["net_income"]), _sum4(i["net_income"], 4)
    finance_ttm = _sum4(i["finance_expense"])
    depreciation_ttm, depreciation_prev = _sum4(i["depreciation"]), _sum4(i["depreciation"], 4)
    sga_ttm, sga_prev = _sum4(i["sga"]), _sum4(i["sga"], 4)
    tax_ttm = _sum4(i["tax_expense"])
    cfo_ttm = _sum4(c["cfo"])
    capex_ttm = _sum4(c["capex"])

    revenue_q = _latest(i["revenue"])
    gross_q = _latest(i["gross_profit"])
    ebit_q = _latest(i["operating_profit"])
    ebitda_q = _latest(i["ebitda"])
    net_q = _latest(i["net_income"])

    avg_assets = _avg(assets, assets_prev)
    avg_equity = _avg(equity, equity_prev)
    avg_inventory = _avg(inventory, inventory_prev)
    avg_receivables = _avg(receivables, receivables_prev)
    avg_payables = _avg(payables, payables_prev)
    cogs_ttm = None if revenue_ttm is None or gross_ttm is None else revenue_ttm - gross_ttm

    current_ratio = _ratio(current_assets, current_liabilities)
    current_ratio_prev = _ratio(current_assets_prev, current_liabilities_prev)
    quick_ratio = _ratio(None if current_assets is None or inventory is None else current_assets - inventory, current_liabilities)
    cash_ratio = _ratio(cash, current_liabilities)
    financial_debt_ratio = _ratio(debt, assets, 100.0)
    leverage_ratio = _ratio(assets, equity)
    liabilities_equity = _ratio(liabilities, equity)
    asset_turnover = _ratio(revenue_ttm, avg_assets)
    asset_turnover_prev = _ratio(revenue_prev, assets_prev)
    inventory_turnover = _ratio(cogs_ttm, avg_inventory)
    payables_turnover = _ratio(cogs_ttm, avg_payables)
    equity_turnover = _ratio(revenue_ttm, avg_equity)
    receivables_turnover = _ratio(revenue_ttm, avg_receivables)
    roa = _ratio(net_ttm, avg_assets, 100.0)
    roa_prev = _ratio(net_prev, assets_prev, 100.0)
    roe = _ratio(net_ttm, avg_equity, 100.0)
    gross_margin = _ratio(gross_ttm, revenue_ttm, 100.0)
    gross_margin_prev = _ratio(gross_prev, revenue_prev, 100.0)
    gross_margin_q = _ratio(gross_q, revenue_q, 100.0)
    ebitda_margin = _ratio(ebitda_ttm, revenue_ttm, 100.0)
    ebitda_margin_q = _ratio(ebitda_q, revenue_q, 100.0)
    operating_margin = _ratio(ebit_ttm, revenue_ttm, 100.0)
    operating_margin_q = _ratio(ebit_q, revenue_q, 100.0)
    net_margin = _ratio(net_ttm, revenue_ttm, 100.0)
    net_margin_q = _ratio(net_q, revenue_q, 100.0)

    net_debt = None if debt is None else debt - (cash or 0.0)
    net_debt_ebitda = _ratio(net_debt, ebitda_ttm)
    interest_coverage = _ratio(ebit_ttm, abs(finance_ttm)) if finance_ttm not in (None, 0) else None
    fcf = None if cfo_ttm is None else cfo_ttm - abs(capex_ttm or 0.0)
    tax_rate = _ratio(abs(tax_ttm), ebit_ttm) if tax_ttm is not None and ebit_ttm not in (None, 0) else None
    if tax_rate is not None:
        tax_rate = float(np.clip(tax_rate, 0.0, 0.35))
    nopat = None if ebit_ttm is None or tax_rate is None else ebit_ttm * (1.0 - tax_rate)
    invested_capital = None if equity is None or debt is None else equity + debt - (cash or 0.0)
    roic = _ratio(nopat, invested_capital, 100.0)

    market = _market_snapshot(fundamental.symbol, fundamental.price)
    shares = market.get("shares_outstanding")
    eps = _ratio(net_ttm, shares)
    bvps = _ratio(equity, shares)
    graham = math.sqrt(22.5 * eps * bvps) if eps is not None and bvps is not None and eps > 0 and bvps > 0 else None

    working_capital = None if current_assets is None or current_liabilities is None else current_assets - current_liabilities
    retained = _latest(b["retained_earnings"])
    ppe = _latest(b["ppe"])
    ppe_prev = _latest(b["ppe"], 4)
    paid_capital = _latest(b["paid_in_capital"])
    paid_capital_prev = _latest(b["paid_in_capital"], 4)

    altman = _altman(
        assets=assets, liabilities=liabilities, working_capital=working_capital, retained_earnings=retained,
        ebit=ebit_ttm, market_cap=market.get("market_cap"), revenue=revenue_ttm,
    )
    beneish = _beneish(
        revenue=revenue_ttm, revenue_prev=revenue_prev, receivables=receivables, receivables_prev=receivables_prev,
        gross_profit=gross_ttm, gross_profit_prev=gross_prev, current_assets=current_assets,
        current_assets_prev=current_assets_prev, ppe=ppe, ppe_prev=ppe_prev, assets=assets, assets_prev=assets_prev,
        depreciation=depreciation_ttm, depreciation_prev=depreciation_prev, sga=sga_ttm, sga_prev=sga_prev,
        liabilities=liabilities, liabilities_prev=liabilities_prev, net_income=net_ttm, cfo=cfo_ttm,
    )
    piotroski = _piotroski(
        roa=roa, roa_prev=roa_prev, cfo=cfo_ttm, net_income=net_ttm, leverage=_ratio(debt, assets),
        leverage_prev=_ratio(debt_prev, assets_prev), current_ratio=current_ratio, current_ratio_prev=current_ratio_prev,
        paid_capital=paid_capital, paid_capital_prev=paid_capital_prev, gross_margin=gross_margin,
        gross_margin_prev=gross_margin_prev, asset_turnover=asset_turnover, asset_turnover_prev=asset_turnover_prev,
    )
    beta = _beta(fundamental.symbol)

    metrics.update({
        "current_ratio": current_ratio, "quick_ratio": quick_ratio, "cash_ratio": cash_ratio,
        "financial_debt_ratio": financial_debt_ratio, "leverage_ratio": leverage_ratio,
        "liabilities_equity": liabilities_equity, "asset_turnover": asset_turnover,
        "inventory_turnover": inventory_turnover, "payables_turnover": payables_turnover,
        "equity_turnover": equity_turnover, "receivables_turnover": receivables_turnover,
        "roa": roa, "roe": roe, "gross_margin": gross_margin, "gross_margin_quarterly": gross_margin_q,
        "ebitda_margin": ebitda_margin, "ebitda_margin_quarterly": ebitda_margin_q,
        "operating_margin": operating_margin, "operating_margin_quarterly": operating_margin_q,
        "net_margin": net_margin, "net_margin_quarterly": net_margin_q, "roic": roic, "eps": eps,
        "book_value_per_share": bvps, "revenue_ttm": revenue_ttm, "gross_profit_ttm": gross_ttm,
        "operating_profit_ttm": ebit_ttm, "ebitda_ttm": ebitda_ttm, "net_income_ttm": net_ttm,
        "cfo_ttm": cfo_ttm, "fcf_ttm": fcf, "assets": assets, "equity": equity,
        "liabilities": liabilities, "total_financial_debt": debt, "cash": cash,
        "market_cap": market.get("market_cap"), "enterprise_value": market.get("enterprise_value"),
        "shares_outstanding": shares, "beta": beta,
    })
    enriched["metrics"] = metrics
    enriched["ratio_groups"] = tuple(
        {"name": group_name, "rows": tuple({"key": key, "label": label, "unit": unit, "value": metrics.get(key)} for key, label, unit in rows)}
        for group_name, rows in RATIO_GROUPS
    )
    enriched["forensic_scores"] = {
        "altman_z": altman,
        "beneish_m": beneish,
        "graham_number": {"value": None if graham is None else round(graham, 3), "coverage": 1.0 if graham is not None else 0.0, "label": "Graham sayısı"},
        "piotroski_f": piotroski,
        "beta": {"value": None if beta is None else round(beta, 3), "coverage": 1.0 if beta is not None else 0.0, "label": "BIST 100'e göre 1 yıllık günlük beta"},
    }
    enriched["ratio_note"] = (
        "Oranlar mümkün olduğunda son 4 çeyrek (TTM) ve son bilanço kullanılarak hesaplanır. "
        "Çeyreklik marjlar yalnız son raporlanan çeyreği gösterir."
    )
    return enriched


def enrich_valuation(
    valuation: dict[str, Any],
    financial: dict[str, Any],
    *,
    symbol: str,
    profile: str,
) -> dict[str, Any]:
    """Add statement-derived multiples and sector/competitor comparison."""
    result = dict(valuation)
    detail = {key: dict(value) if isinstance(value, dict) else value for key, value in valuation.get("metrics", {}).items()}
    fm = financial.get("metrics", {})

    market_cap = _finite(fm.get("market_cap"))
    enterprise = _finite(fm.get("enterprise_value"))
    debt = _finite(fm.get("total_financial_debt"))
    cash = _finite(fm.get("cash"))
    if enterprise is None and market_cap is not None and debt is not None:
        enterprise = market_cap + debt - (cash or 0.0)
    revenue = _finite(fm.get("revenue_ttm"))
    ebitda = _finite(fm.get("ebitda_ttm"))
    net_income = _finite(fm.get("net_income_ttm"))
    fcf = _finite(fm.get("fcf_ttm"))
    pe = _finite(detail.get("pe", {}).get("value")) if isinstance(detail.get("pe"), dict) else None
    if pe is None:
        pe = _ratio(market_cap, net_income)
    pb = _finite(detail.get("pb", {}).get("value")) if isinstance(detail.get("pb"), dict) else None
    if pb is None:
        pb = _ratio(market_cap, _finite(fm.get("equity")))
    ev_ebitda = _ratio(enterprise, ebitda)
    ev_sales = _ratio(enterprise, revenue)
    ps = _ratio(market_cap, revenue)
    p_fcf = _ratio(market_cap, fcf)
    earnings_yield = _ratio(net_income, market_cap, 100.0)
    fcf_yield = _ratio(fcf, market_cap, 100.0)
    growth = _finite(fm.get("net_income_growth"))
    peg = pe / growth if pe is not None and pe > 0 and growth is not None and growth > 0 else None

    for key, value in (
        ("pe", pe), ("pb", pb), ("ev_ebitda", ev_ebitda), ("ev_sales", ev_sales), ("ps", ps),
        ("p_fcf", p_fcf), ("peg", peg), ("earnings_yield", earnings_yield), ("fcf_yield", fcf_yield),
    ):
        existing = detail.get(key)
        if isinstance(existing, dict):
            existing = dict(existing)
            if existing.get("value") is None and value is not None:
                existing["value"] = value
            detail[key] = existing
        else:
            detail[key] = {"value": value, "percentile": None}

    peer_analysis: dict[str, Any] = {"scope": result.get("scope", "—"), "peer_count": 0, "peers": [], "benchmarks": {}}
    try:
        frame = core._fetch_peer_snapshot()
        row = frame[frame["symbol"] == symbol]
        if not row.empty:
            sector = str(row.iloc[0].get("sector") or "GENERIC")
            industry = str(row.iloc[0].get("industry") or "")
            industry_peers = frame[frame["industry"] == industry] if industry and "industry" in frame.columns else pd.DataFrame()
            sector_peers = frame[frame["sector"] == sector] if sector != "GENERIC" else pd.DataFrame()
            if len(industry_peers) >= 5:
                peers = industry_peers.copy()
                scope = f"{industry} endüstrisi"
            elif len(sector_peers) >= 8:
                peers = sector_peers.copy()
                scope = f"{sector} sektörü"
            else:
                peers = frame.copy()
                scope = "BIST geneli"

            benchmarks: dict[str, Any] = {}
            for metric in ("pe", "pb", "ev_ebitda", "ev_sales", "roe"):
                if metric not in peers.columns:
                    continue
                series = pd.to_numeric(peers[metric], errors="coerce")
                if metric != "roe":
                    series = series.where(series > 0)
                clean = series.dropna()
                target = _finite(row.iloc[0].get(metric))
                if len(clean) < 5:
                    continue
                benchmarks[metric] = {
                    "median": float(clean.median()), "q1": float(clean.quantile(0.25)), "q3": float(clean.quantile(0.75)),
                    "target": target, "percentile": None if target is None else round(float((clean <= target).mean() * 100.0), 1),
                }

            if "market_cap" in peers.columns:
                peers = peers.assign(_market_cap_num=pd.to_numeric(peers["market_cap"], errors="coerce")).sort_values(
                    "_market_cap_num", ascending=False, na_position="last"
                )
            selected = peers.head(8)
            peers_payload = []
            for _, peer_row in selected.iterrows():
                peer_payload = {"symbol": str(peer_row.get("symbol", "")), "name": str(peer_row.get("name", "") or "")}
                for metric in ("market_cap", "pe", "pb", "ev_ebitda", "ev_sales", "roe"):
                    peer_payload[metric] = _finite(peer_row.get(metric))
                peers_payload.append(peer_payload)
            peer_analysis = {
                "scope": scope, "sector": sector, "industry": industry, "peer_count": int(len(peers)),
                "peers": peers_payload, "benchmarks": benchmarks,
            }
            result["scope"] = scope
            result["sector"] = sector
    except Exception as exc:  # noqa: BLE001
        peer_analysis["error"] = type(exc).__name__

    result["metrics"] = detail
    result["peer_analysis"] = peer_analysis
    result["peg_note"] = (
        "PEG, analist ileriye dönük tahmini yerine mevcut F/K'nın son 4 çeyrek net kâr yıllık büyümesine "
        "bölünmesiyle hesaplanır; büyüme negatif/sıfırsa gösterilmez."
    )
    result["calculated_multiples"] = {
        "market_cap": market_cap, "enterprise_value": enterprise, "pe": pe, "pb": pb, "ev_ebitda": ev_ebitda,
        "ev_sales": ev_sales, "ps": ps, "p_fcf": p_fcf, "peg": peg, "earnings_yield": earnings_yield, "fcf_yield": fcf_yield,
    }
    if profile == "BANK":
        result["note"] = (
            "Banka değerlemesinde F/K, PD/DD ve ROE ana eksendir. FD/FAVÖK, FD/Satış ve endüstriyel "
            "likidite/kaldıraç oranları karar metriği olarak kullanılmaz."
        )
    elif profile == "GYO":
        result["note"] = (
            "GYO için PD/DD ve kârlılık çarpanları gösterilir; gerçek NAD/NAV ve ekspertiz portföyü "
            "sağlayıcıdan alınamadıkça PD/NAD üretilmez."
        )
    return result
