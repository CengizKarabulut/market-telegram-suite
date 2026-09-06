"""Company-type valuation policy for the integrated research report.

The policy follows the user's valuation workflow: choose the economically correct
model first, test whether the required evidence exists, and report unusable models
instead of forcing a target price.  Relative valuation remains a secondary market
context; it is not treated as intrinsic value.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from src import valuation_models as vm

STATUS_SUITABLE = "UYGUN"
STATUS_CONDITIONAL = "KOŞULLU"
STATUS_UNSUITABLE = "UYGUN DEĞİL"
STATUS_MISSING = "VERİ EKSİK"


@dataclass(frozen=True)
class ModelAssessment:
    model: str
    status: str
    role: str
    reason: str
    value_per_share: float | None = None
    confidence: float = 0.0
    assumptions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _profile(profile: str, sector: str) -> str:
    raw = f"{profile} {sector}".casefold()
    if "bank" in raw or "banka" in raw:
        return "BANK"
    if profile == "GYO" or "gyo" in raw or "reit" in raw or "gayrimenkul" in raw:
        return "GYO"
    if "holding" in raw or "yatırım ortak" in raw or "yatirim ortak" in raw:
        return "HOLDING"
    return "GENERIC"


def _model(model: str, status: str, role: str, reason: str, **kwargs: Any) -> ModelAssessment:
    return ModelAssessment(model=model, status=status, role=role, reason=reason, **kwargs)


def _relative_assessment(peer: dict[str, Any]) -> ModelAssessment:
    score = _finite(peer.get("score"))
    coverage = _finite(peer.get("coverage")) or 0.0
    if score is None or coverage < 0.35:
        return _model(
            "Göreli Çarpanlar",
            STATUS_MISSING,
            "ikincil",
            "Akran evreni veya karşılaştırılabilir çarpan kapsamı yeterli değil.",
            confidence=coverage,
        )
    return _model(
        "Göreli Çarpanlar",
        STATUS_SUITABLE,
        "ikincil",
        "Sektör/akran konumunu gösterir; tek başına içsel değer veya şirket kalitesi sayılmaz.",
        confidence=coverage,
    )


def _gyo_models(metrics: dict[str, Any], peer: dict[str, Any]) -> list[ModelAssessment]:
    assessments = [
        _model(
            "NAD / NAV",
            STATUS_MISSING,
            "birincil",
            "GYO için birincil yöntem ekspertiz bazlı portföy gerçeğe uygun değeridir. "
            "Portföy ekspertiz tablosu, finansal borçlar ve diğer yükümlülükler olmadan gerçek NAD üretilmez.",
            confidence=0.0,
            assumptions=("KAP/şirket ekspertiz portföyü", "yükümlülük ayrıntısı", "hisse adedi"),
        ),
        _relative_assessment(peer),
    ]
    cfo_ni = _finite(metrics.get("cfo_net_income"))
    fcf_margin = _finite(metrics.get("fcf_margin"))
    if cfo_ni is None or fcf_margin is None:
        dcf_status = STATUS_MISSING
        dcf_reason = "Tekrarlayan nakit akışının kâra dönüşümü yeterince ölçülemiyor; klasik DCF zorlanmadı."
    elif cfo_ni > 0.7 and fcf_margin > 0:
        dcf_status = STATUS_CONDITIONAL
        dcf_reason = "Pozitif nakit dönüşümü DCF'i yardımcı model yapabilir; ancak GYO'da NAD'ın yerini almaz ve WACC/g varsayımları ayrıca gerekir."
    else:
        dcf_status = STATUS_UNSUITABLE
        dcf_reason = "Muhasebe kârının nakit karşılığı zayıf/negatif; klasik FCFF DCF bu görünümde ekonomik olarak güvenilir değil."
    assessments.extend(
        [
            _model("FCFF DCF", dcf_status, "yardımcı", dcf_reason, confidence=0.35 if dcf_status == STATUS_CONDITIONAL else 0.0),
            _model(
                "F/K",
                STATUS_UNSUITABLE,
                "kontrol",
                "GYO kârı yeniden değerleme ve nakit olmayan kalemlerden etkilenebildiği için F/K birincil değerleme değildir.",
            ),
            _model("Residual Income", STATUS_UNSUITABLE, "—", "Banka/finansal özkaynak modeli; GYO için birincil yöntem değildir."),
        ]
    )
    return assessments


def _bank_models(metrics: dict[str, Any], peer: dict[str, Any]) -> list[ModelAssessment]:
    roe_pct = _finite(metrics.get("roe"))
    pb = _finite(metrics.get("pb"))
    residual_status = STATUS_CONDITIONAL if roe_pct is not None and pb is not None and pb > 0 else STATUS_MISSING
    return [
        _model(
            "Residual Income",
            residual_status,
            "birincil",
            "Bankalarda capex/işletme sermayesi FCFF mantığı yerine defter değeri ile ROE'nin özkaynak maliyetini aşan kısmı esastır. "
            "Sayısal değer için sürdürülebilir ROE, Ke ve dağıtım oranı senaryosu gerekir.",
            confidence=0.55 if residual_status == STATUS_CONDITIONAL else 0.0,
        ),
        _model(
            "Haklı PD/DD",
            residual_status,
            "birincil/çapraz kontrol",
            "ROE ile özkaynak maliyeti arasındaki fark PD/DD'nin ekonomik temelidir; Ke ve uzun dönem g verilmeden hedef çarpan uydurulmaz.",
            confidence=0.5 if residual_status == STATUS_CONDITIONAL else 0.0,
        ),
        _relative_assessment(peer),
        _model("Temettü İskonto", STATUS_CONDITIONAL, "yardımcı", "Düzenli ve sürdürülebilir dağıtım politikası varsa kullanılabilir; ileri temettü tahmini gerekir."),
        _model("FCFF / FD-FAVÖK", STATUS_UNSUITABLE, "—", "Banka bilançosunda borç işletme hammaddesidir; klasik firma değeri/FCFF yaklaşımı uygun değildir."),
        _model("Altman Z", STATUS_UNSUITABLE, "—", "Bankalar için imalat şirketi iflas modeli ekonomik olarak uygun değildir."),
    ]


def _generic_models(metrics: dict[str, Any], peer: dict[str, Any], *, holding: bool = False) -> list[ModelAssessment]:
    cfo_ni = _finite(metrics.get("cfo_net_income"))
    fcf_margin = _finite(metrics.get("fcf_margin"))
    op_growth = _finite(metrics.get("operating_growth"))
    if cfo_ni is None or fcf_margin is None:
        dcf_status = STATUS_MISSING
        dcf_reason = "FCF/nakit dönüşümü yeterli değil; DCF için projeksiyon tabanı doğrulanamıyor."
    elif cfo_ni > 0.7 and fcf_margin > 0:
        dcf_status = STATUS_CONDITIONAL
        dcf_reason = "Nakit dönüşümü DCF'e elverişli; sayısal içsel değer için şirket-spesifik FCFF tahmini, WACC ve terminal büyüme gerekir."
    else:
        dcf_status = STATUS_UNSUITABLE
        dcf_reason = "FCF veya nakit/kâr dönüşümü zayıf; mevcut muhasebe kârından zorla DCF hedefi üretilmedi."
    epv_status = STATUS_CONDITIONAL if op_growth is not None else STATUS_MISSING
    assessments = [
        _model("FCFF DCF", dcf_status, "birincil", dcf_reason, confidence=0.5 if dcf_status == STATUS_CONDITIONAL else 0.0),
        _model(
            "EPV / Kazanç Gücü",
            epv_status,
            "taban değer",
            "Normalize faaliyet kârıyla büyümesiz taban değer üretilebilir; normalize EBIT, idame capex, net borç ve WACC gerekir.",
            confidence=0.4 if epv_status == STATUS_CONDITIONAL else 0.0,
        ),
        _relative_assessment(peer),
        _model("Piotroski F-Score", STATUS_CONDITIONAL, "kalite kontrolü", "En az iki karşılaştırılabilir bilanço dönemi ve hisse adedi/temel marj verileriyle finansal sağlamlık kontrolü yapılabilir."),
        _model("Altman Z", STATUS_CONDITIONAL, "risk kontrolü", "İmalat/operasyonel şirketlerde yardımcı iflas riski göstergesidir; GYO/banka için kullanılmamalıdır."),
    ]
    if holding:
        assessments.insert(
            0,
            _model(
                "NAD / SOTP",
                STATUS_MISSING,
                "birincil",
                "Holdinglerde iştirak/varlıkların ayrı gerçeğe uygun değerleri ve net borç olmadan SOTP/NAD üretilmez.",
                assumptions=("iştirak piyasa/gerçeğe uygun değerleri", "holding net borcu"),
            ),
        )
        assessments[1] = _model("FCFF DCF", STATUS_CONDITIONAL, "yardımcı", "Holding seviyesinde DCF ancak tekrar eden merkez nakit akışı anlamlıysa yardımcı modeldir.")
    return assessments


def build_valuation_policy(
    profile: str,
    sector: str,
    metrics: dict[str, Any],
    peer_valuation: dict[str, Any],
    price: float | None = None,
) -> dict[str, Any]:
    """Return an evidence-bound valuation matrix without fabricating assumptions."""
    kind = _profile(profile, sector)
    if kind == "GYO":
        models = _gyo_models(metrics, peer_valuation)
        primary = "NAD / NAV"
    elif kind == "BANK":
        models = _bank_models(metrics, peer_valuation)
        primary = "Residual Income + Haklı PD/DD"
    elif kind == "HOLDING":
        models = _generic_models(metrics, peer_valuation, holding=True)
        primary = "NAD / SOTP"
    else:
        models = _generic_models(metrics, peer_valuation)
        primary = "FCFF DCF"

    peer_score = _finite(peer_valuation.get("score"))
    peer_coverage = _finite(peer_valuation.get("coverage")) or 0.0
    usable = [item for item in models if item.status in {STATUS_SUITABLE, STATUS_CONDITIONAL}]
    model_coverage = len(usable) / max(len(models), 1)
    confidence = round(min(1.0, 0.6 * peer_coverage + 0.4 * model_coverage), 2)

    result = dict(peer_valuation)
    result.update(
        {
            "score": peer_score,
            "coverage": peer_coverage,
            "profile": kind,
            "primary_model": primary,
            "model_confidence": confidence,
            "model_coverage": round(model_coverage, 2),
            "models": [item.to_dict() for item in models],
            "computed_values": {},
            "price": _finite(price),
            "policy_note": (
                "Model uygunluğu puandan önce gelir. Uygun olmayan veya girdisi eksik model çalıştırılmaz; "
                "tek hedef fiyat yerine uygun olduğunda duyarlılık/dağılım raporlanır."
            ),
        }
    )
    return result


def evaluate_nav_if_available(
    valuation: dict[str, Any],
    *,
    portfolio_fair_value: float | None,
    cash: float | None,
    receivables: float | None,
    other_assets: float | None,
    financial_debt: float | None,
    other_liabilities: float | None,
    minority_interest: float | None,
    shares_outstanding: float | None,
    price: float | None,
) -> dict[str, Any]:
    """Optional hook for KAP/appraisal data; leaves valuation untouched when incomplete."""
    required = [portfolio_fair_value, shares_outstanding]
    if any(_finite(value) is None for value in required):
        return valuation
    nav = vm.nav_per_share(
        vm.NAVInputs(
            portfolio_fair_value=float(portfolio_fair_value),
            cash_and_equivalents=float(cash or 0.0),
            receivables=float(receivables or 0.0),
            other_assets=float(other_assets or 0.0),
            financial_debt=float(financial_debt or 0.0),
            other_liabilities=float(other_liabilities or 0.0),
            minority_interest=float(minority_interest or 0.0),
            shares_outstanding=float(shares_outstanding),
        )
    )
    computed = dict(valuation.get("computed_values") or {})
    computed["nav"] = nav
    if _finite(price) is not None:
        computed["nav_market_relation"] = vm.nav_premium(float(price), float(nav["nav_per_share"]))
    result = dict(valuation)
    result["computed_values"] = computed
    result["primary_model"] = "NAD / NAV"
    result["model_confidence"] = max(float(result.get("model_confidence") or 0.0), 0.8)
    models = []
    for item in result.get("models", []):
        updated = dict(item)
        if item.get("model") == "NAD / NAV":
            updated.update(
                {
                    "status": STATUS_SUITABLE,
                    "value_per_share": nav["nav_per_share"],
                    "confidence": 0.9,
                    "reason": "Ekspertiz/gerçeğe uygun portföy değeri ve yükümlülük girdileriyle gerçek NAD hesaplandı.",
                }
            )
        models.append(updated)
    result["models"] = models
    return result
