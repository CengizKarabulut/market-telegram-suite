from __future__ import annotations

import math
from typing import Any

from .models import LevelClass, LevelLifecycle, MarketState, TechnicalLevel


LIVE_SCANNER_STATES = {"NEW", "ACTIVE", "CONFIRMED"}
NON_ACTIONABLE_LEVEL_STATES = {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _section(state: MarketState, name: str) -> dict[str, Any]:
    features = state.technical_features or {}
    sections = features.get("sections") if features.get("available") else {}
    item = (sections or {}).get(name) or {}
    return dict(item) if isinstance(item, dict) else {}


def _fmt_price(value: Any) -> str:
    number = _number(value)
    return f"{number:.2f}" if number is not None else "—"


def _nearest_level(state: MarketState, side: str) -> TechnicalLevel | None:
    candidates = [
        level
        for level in state.levels
        if level.lifecycle_state not in NON_ACTIONABLE_LEVEL_STATES
        and level.level_class != LevelClass.STRUCTURAL
        and (
            (side == "ABOVE" and level.value > state.price)
            or (side == "BELOW" and level.value < state.price)
        )
    ]
    return min(candidates, key=lambda item: abs(item.value - state.price), default=None)


def _ma_zone(state: MarketState, side: str) -> tuple[float, float] | None:
    rows = [
        item
        for item in (state.ma_level_evidence or [])
        if str(item.get("side") or "") == side
    ]
    if not rows:
        return None

    def distance(item: dict[str, Any]) -> float:
        value = _number(item.get("distance_atr"))
        return abs(value) if value is not None else math.inf

    rows.sort(key=distance)
    chosen = rows[:2]
    values: list[float] = []
    for item in chosen:
        for key in ("zone_low", "zone_mid", "zone_high"):
            value = _number(item.get(key))
            if value is not None:
                values.append(value)
    if not values:
        return None
    return min(values), max(values)


def _zone_text(zone: tuple[float, float] | None) -> str | None:
    if zone is None:
        return None
    low, high = zone
    if math.isclose(low, high, rel_tol=0.0, abs_tol=0.005):
        return _fmt_price(low)
    return f"{_fmt_price(low)}–{_fmt_price(high)}"


def _scanner_context(state: MarketState) -> dict[str, Any]:
    rows = list(state.scanner_evidence or [])
    live = [item for item in rows if str(item.get("state") or "").upper() in LIVE_SCANNER_STATES]
    historical = [item for item in rows if str(item.get("state") or "").upper() == "HISTORICAL"]
    live_sides = {str(item.get("side") or "NEUTRAL").upper() for item in live}
    historical_sides = {str(item.get("side") or "NEUTRAL").upper() for item in historical}
    return {
        "live_sides": live_sides,
        "historical_sides": historical_sides,
        "live_count": len(live),
        "historical_count": len(historical),
    }


def _headline(state: MarketState) -> str:
    synthesis_state = str((state.technical_synthesis or {}).get("state") or "")
    price_position = str((state.structure or {}).get("price_position") or "")
    if synthesis_state == "BULLISH_ALIGNMENT":
        return "Görünüm olumlu; fiyat yapısı ve kısa vadeli güç aynı yönde çalışıyor."
    if synthesis_state == "BEARISH_ALIGNMENT":
        return "Baskı sürüyor; fiyat yapısı ve kısa vadeli güç henüz toparlanmayı doğrulamıyor."
    if synthesis_state == "EARLY_RECOVERY":
        return "Toparlanma işaretleri var, ancak bunu kalıcı trend dönüşü saymak için henüz erken."
    if synthesis_state == "BULLISH_STRUCTURE_WITH_PULLBACK":
        return "Ana görünüm olumlu kalırken kısa vadede bir soluklanma ve güç kaybı var."
    if synthesis_state == "HIGH_UNCERTAINTY":
        return "Hissede yön net değil; fiyatın yakın destek ve dirençlere vereceği tepki belirleyici olacak."
    if price_position == "BELOW_STRUCTURE":
        return "Hisse zayıf bölgede; mevcut fiyat hareketi henüz güvenilir bir dönüş teyidi üretmiş değil."
    if price_position == "ABOVE_STRUCTURE":
        return "Fiyat güçlü bölgede; görünümün korunması için yakın desteklerin üzerinde kalıcılık önemli."
    return "Görünüm karışık; belirgin bir üstünlük oluşmadan önce fiyat teyidi gerekiyor."


def _overview(state: MarketState) -> str:
    structure = state.structure or {}
    bias = str(structure.get("bias") or "TRANSITION")
    price_position = str(structure.get("price_position") or "UNAVAILABLE")
    trend = _section(state, "trend_and_averages")
    trend_state = str(trend.get("state") or "INSUFFICIENT")
    relative = state.relative_strength or {}

    sentences: list[str] = []
    if price_position == "BELOW_STRUCTURE":
        sentences.append("Fiyat son teyitli hareket alanının altında kaldığı için ana baskı henüz ortadan kalkmış değil.")
    elif price_position == "ABOVE_STRUCTURE":
        sentences.append("Fiyat son teyitli hareket alanının üzerinde; ana görüntü şimdilik alıcıların lehine.")
    elif bias == "BULLISH":
        sentences.append("Tepe ve dip yapısı yükseliş eğilimini koruyor.")
    elif bias == "BEARISH":
        sentences.append("Tepe ve dip yapısı aşağı yönlü; dönüş için önce bu yapının bozulması gerekiyor.")
    else:
        sentences.append("Son tepe ve dipler net bir trend üretmiyor; hisse geçiş bölgesinde.")

    if trend_state == "NEGATIVE":
        sentences.append("Kısa ve orta vadeli eğilim de aşağı yönlü olduğu için yükseliş denemeleri şimdilik tepki niteliğinde kalabilir.")
    elif trend_state == "POSITIVE":
        sentences.append("Kısa ve orta vadeli eğilim yukarı yönü destekliyor.")
    elif trend_state == "MIXED":
        sentences.append("Kısa ve orta vadeli eğilim aynı yönde değil; bu nedenle hareketin devamlılığı henüz net değil.")

    if relative.get("available"):
        rs_state = str(relative.get("state") or "")
        benchmark = str(relative.get("benchmark") or "endeks")
        if rs_state == "UNDERPERFORMING":
            sentences.append(f"Hisse ayrıca {benchmark} karşısında geride kalıyor; göreceli güç henüz toparlanmış değil.")
        elif rs_state == "OUTPERFORMING":
            sentences.append(f"{benchmark} karşısındaki göreceli performans hisseden yana.")
    return " ".join(sentences[:3])


def _momentum_text(state: MarketState) -> str:
    momentum = _section(state, "momentum")
    momentum_state = str(momentum.get("state") or "INSUFFICIENT")
    changes = state.technical_changes or {}
    events = list(changes.get("events") or [])
    positive_momentum_change = any(
        item.get("family") == "MOMENTUM" and item.get("effect") == "POSITIVE"
        for item in events
    )
    negative_momentum_change = any(
        item.get("family") == "MOMENTUM" and item.get("effect") == "NEGATIVE"
        for item in events
    )

    if momentum_state == "POSITIVE" and negative_momentum_change:
        return "Alım isteği hâlâ olumlu bölgede, ancak son seansta ivme kaybı başladı; güçlenmenin devamı teyit bekliyor."
    if momentum_state == "POSITIVE":
        return "Kısa vadeli alım isteği canlı; fiyatın bunu yeni tepe ve hacim desteğiyle doğrulaması görünümü güçlendirir."
    if momentum_state == "NEGATIVE" and positive_momentum_change:
        return "Kısa vadeli göstergeler hâlâ zayıf, fakat son seansta ilk toparlanma belirtileri oluştu; bu henüz trend dönüşü anlamına gelmiyor."
    if momentum_state == "NEGATIVE" and negative_momentum_change:
        return "Alım isteği zayıf ve son seansta ivme biraz daha bozuldu; kısa vadede baskının hafiflediğine dair net işaret yok."
    if momentum_state == "NEGATIVE":
        return "Kısa vadeli alım isteği zayıf; toparlanmanın kalıcı sayılması için momentumun yeniden güç kazanması gerekiyor."
    if momentum_state == "MIXED":
        return "Kısa vadeli göstergeler birbirini doğrulamıyor; bazı toparlanma izleri olsa da net bir momentum üstünlüğü yok."
    return "Kısa vadeli momentum için yeterli veri yok."


def _participation_text(state: MarketState) -> str:
    participation = _section(state, "participation")
    participation_state = str(participation.get("state") or "INSUFFICIENT")
    rvol = _number(participation.get("rvol"))
    change = _number(state.change_pct) or 0.0
    ratio_text = f" ({rvol:.2f}x)" if rvol is not None else ""

    if participation_state == "STRONG_PARTICIPATION":
        if change > 0:
            return f"Yükseliş normalin belirgin üzerinde hacimle destekleniyor{ratio_text}; bu, alıcı katılımının ciddiye alınması gerektiğini gösteriyor."
        if change < 0:
            return f"Düşüş yüksek hacimle gerçekleşiyor{ratio_text}; satış baskısının sıradan bir geri çekilmeden daha güçlü olma riski var."
        return f"İşlem hacmi normalin belirgin üzerinde{ratio_text}; fiyatın hangi yönde kırıldığı bu katılımın anlamını belirleyecek."
    if participation_state == "LOW_PARTICIPATION":
        if change > 0:
            return f"Fiyat yükselse de hacim zayıf{ratio_text}; hareket henüz güçlü alıcı katılımıyla teyit edilmiyor."
        if change < 0:
            return f"Fiyat geriliyor ancak hacim zayıf{ratio_text}; güçlü bir satış dalgası görünmüyor, fakat alıcı ilgisi de düşük."
        return f"Hacim normalin altında{ratio_text}; piyasadaki katılım zayıf olduğu için yön sinyallerinin güveni sınırlı."
    if participation_state == "NORMAL_PARTICIPATION":
        return f"Hacim normal aralıkta{ratio_text}; fiyat hareketini destekliyor ama tek başına güçlü bir teyit oluşturmuyor."
    return "Hacim katılımı için yeterli veri yok."


def _screening_text(state: MarketState) -> str:
    context = _scanner_context(state)
    live_sides = context["live_sides"]
    historical_sides = context["historical_sides"]
    structure_bias = str((state.structure or {}).get("bias") or "TRANSITION")

    if "BUY" in live_sides and "SELL" in live_sides:
        return "Kısa vadeli teknik taramalarda hem olumlu hem olumsuz koşullar aynı anda görülüyor; bu nedenle tek yönlü bir teyit yok."
    if "BUY" in live_sides:
        if structure_bias == "BEARISH":
            return "Bazı kısa vadeli teknik koşullar toparlanma ihtimaline işaret ediyor, ancak ana fiyat yapısı henüz bu dönüşü doğrulamıyor."
        return "Kısa vadeli teknik taramalarda olumlu koşullar oluşmuş; bunların fiyat yapısı ve hacimle teyit edilmesi önemli."
    if "SELL" in live_sides:
        if structure_bias == "BULLISH":
            return "Kısa vadeli teknik taramalarda zayıflama görülüyor, ancak ana yükseliş yapısı henüz tamamen bozulmuş değil."
        return "Kısa vadeli teknik taramalar mevcut baskının sürdüğünü destekliyor."
    if "BUY" in historical_sides and "SELL" in historical_sides:
        return "Geçmiş teknik tarama kayıtlarında iki yönlü sinyaller bulunuyor; bunlar bugünkü görünüm için güncel teyit sayılmıyor."
    if "BUY" in historical_sides:
        return "Daha önce kısa vadeli olumlu teknik eşleşmeler görülmüş, ancak bunlar güncel teyit değil; bugünkü fiyat davranışı esas alınmalı."
    if "SELL" in historical_sides:
        return "Daha önce kısa vadeli olumsuz teknik eşleşmeler görülmüş, ancak bunlar güncel teyit değil; bugünkü fiyat davranışı esas alınmalı."
    return "Ek teknik taramalardan güncel yön teyidi gelmiyor."


def _levels_text(state: MarketState) -> str:
    support_zone = _zone_text(_ma_zone(state, "SUPPORT"))
    resistance_zone = _zone_text(_ma_zone(state, "RESISTANCE"))
    lower = _nearest_level(state, "BELOW")
    upper = _nearest_level(state, "ABOVE")

    sentences: list[str] = []
    if resistance_zone:
        sentences.append(f"Yukarıda {resistance_zone} bandı ilk toparlanma eşiği olarak öne çıkıyor.")
    elif upper is not None:
        sentences.append(f"Yukarıda {_fmt_price(upper.value)} ilk önemli aşılması gereken seviye.")

    if support_zone:
        sentences.append(f"Aşağıda {support_zone} civarı kısa vadeli tutunma alanı.")
    if lower is not None:
        lower_text = _fmt_price(lower.value)
        if not support_zone or lower_text not in support_zone:
            sentences.append(f"Bunun altında {lower_text} daha önemli destek/referans bölgesi olarak izlenebilir.")

    if not sentences:
        return "Fiyata yakın, güvenilir bir teknik eşik oluşmuş değil; yeni tepe/dip oluşumu beklenmeli."
    return " ".join(sentences[:3])


def _change_text(state: MarketState) -> str:
    changes = state.technical_changes or {}
    if not changes.get("available"):
        return "Son seanstaki değişimi karşılaştırmak için yeterli veri yok."
    events = list(changes.get("events") or [])
    if not events:
        return "Son seansta teknik görünümü değiştirecek yeni bir kırılım veya belirgin güç değişimi oluşmadı."

    structure_pos = any(item.get("family") == "STRUCTURE" and item.get("effect") == "POSITIVE" for item in events)
    structure_neg = any(item.get("family") == "STRUCTURE" and item.get("effect") == "NEGATIVE" for item in events)
    momentum_pos = any(item.get("family") == "MOMENTUM" and item.get("effect") == "POSITIVE" for item in events)
    momentum_neg = any(item.get("family") == "MOMENTUM" and item.get("effect") == "NEGATIVE" for item in events)
    volume_change = any(item.get("family") == "PARTICIPATION" for item in events)
    trend_pos = any(item.get("family") in {"TREND", "TREND_SYSTEM"} and item.get("effect") == "POSITIVE" for item in events)
    trend_neg = any(item.get("family") in {"TREND", "TREND_SYSTEM"} and item.get("effect") == "NEGATIVE" for item in events)

    pieces: list[str] = []
    if structure_pos:
        pieces.append("Fiyat yapısında olumlu bir kırılma oluştu.")
    elif structure_neg:
        pieces.append("Fiyat yapısında yeni bir bozulma oluştu.")
    if momentum_pos and not momentum_neg:
        pieces.append("Kısa vadeli ivme önceki seansa göre toparlandı.")
    elif momentum_neg and not momentum_pos:
        pieces.append("Kısa vadeli ivme önceki seansa göre zayıfladı.")
    elif momentum_pos and momentum_neg:
        pieces.append("Kısa vadeli göstergelerde aynı anda hem iyileşme hem zayıflama var; değişim karışık.")
    if trend_pos and not trend_neg:
        pieces.append("Trend tarafında ilk iyileşme sinyalleri görülüyor.")
    elif trend_neg and not trend_pos:
        pieces.append("Trend tarafındaki baskı biraz daha arttı.")
    if volume_change:
        participation = _section(state, "participation")
        rvol = _number(participation.get("rvol"))
        if rvol is not None:
            pieces.append(f"Hacim katılımı da değişti ve son değer normalin yaklaşık {rvol:.2f} katında.")
        else:
            pieces.append("Hacim katılımında da belirgin bir değişim var.")
    return " ".join(pieces[:3]) or str(changes.get("headline") or "Son seansta görünümde sınırlı değişim var.")


def _conclusion(state: MarketState) -> str:
    synthesis_state = str((state.technical_synthesis or {}).get("state") or "")
    resistance_zone = _zone_text(_ma_zone(state, "RESISTANCE"))
    support_zone = _zone_text(_ma_zone(state, "SUPPORT"))
    upper = _nearest_level(state, "ABOVE")
    lower = _nearest_level(state, "BELOW")
    upper_text = resistance_zone or (_fmt_price(upper.value) if upper is not None else None)
    lower_text = support_zone or (_fmt_price(lower.value) if lower is not None else None)

    if synthesis_state in {"BEARISH_ALIGNMENT", "MIXED", "NO_CLEAR_EDGE", "HIGH_UNCERTAINTY"} or str((state.structure or {}).get("price_position")) == "BELOW_STRUCTURE":
        first = "Şu aşamada hissede kalıcı güçlenme teyidi yok; olası yukarı tepkileri doğrudan trend dönüşü olarak okumak erken."
        watch: list[str] = []
        if upper_text:
            watch.append(f"Önce {upper_text} bölgesinin geri alınması")
        watch.append("ardından momentum ve hacmin toparlanmayı desteklemesi")
        second = "Görünümün iyileşmesi için " + ", ".join(watch) + " gerekir."
        if lower_text:
            second += f" {lower_text} altındaki kalıcılık ise aşağı yönlü riski artırır."
        return f"{first} {second}"

    if synthesis_state == "EARLY_RECOVERY":
        second = f"{upper_text} üzerine yerleşme" if upper_text else "yakın direncin aşılması"
        return f"Toparlanma denemesi var ama henüz erken aşamada. {second} ve hacim desteği gelirse hareket daha güvenilir hale gelir; aksi halde tepki sınırlı kalabilir."

    first = "Teknik görünüm şu an olumlu, ancak bu durumun devamı fiyatın kazandığı bölgeleri korumasına bağlı."
    details: list[str] = []
    if lower_text:
        details.append(f"{lower_text} üzerinde kalıcılık görünümü destekler")
    if upper_text:
        details.append(f"{upper_text} aşılırsa yeni güçlenme teyidi alınabilir")
    return first + (" " + "; ".join(details) + "." if details else "")


def build_reader_narrative(state: MarketState) -> dict[str, Any]:
    """Ham indikatör isimlerini kullanıcıya dökmeden analist diliyle anlatım üretir.

    Ayrıntılı teknik feature, tarama kodu ve hareketli ortalama isimleri canonical
    raporda korunur; bu katman yalnız son kullanıcıya gösterilecek sade metni üretir.
    Böylece açıklama kaynağını kaybetmeden teknik jargon ve scanner marka/adları
    presentation katmanından çıkarılır.
    """
    if bool(state.confidence.get("critical_data_quality")):
        return {
            "available": False,
            "headline": "Veri kalitesi yeterli olmadığı için güvenilir analiz üretilemiyor.",
            "overview": "Önce fiyat ve kurumsal işlem verisinin doğrulanması gerekiyor.",
            "momentum": "",
            "participation": "",
            "screening": "",
            "levels": "",
            "what_changed": "",
            "conclusion": "Veri sorunu çözülmeden yön çıkarımı yapılmamalı.",
        }
    return {
        "available": True,
        "headline": _headline(state),
        "overview": _overview(state),
        "momentum": _momentum_text(state),
        "participation": _participation_text(state),
        "screening": _screening_text(state),
        "levels": _levels_text(state),
        "what_changed": _change_text(state),
        "conclusion": _conclusion(state),
    }
