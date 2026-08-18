"""Sade dil katmanı.

Teknik rapor uzman için yazılmıştır. Bu modül aynı bulguları teknik terim
kullanmadan, kısa cümlelerle özetler. Amaç basitleştirme değil, erişilebilirlik:
hiçbir yeni iddia üretilmez, yalnızca mevcut sınıflamalar gündelik dile çevrilir.
"""

from __future__ import annotations

import math
from typing import Any

SETUP_PLAIN = {
    "Destekte reddedilme / başarısız aşağı kırılım": (
        "Fiyat aşağı kırmayı denedi ama başaramadı; sarktığı yerden geri döndü."
    ),
    "Dirençte reddedilme / başarısız yukarı kırılım": (
        "Fiyat yukarı çıkmayı denedi ama tutunamadı; yükseldiği yerden geri geldi."
    ),
    "Sıkışma / karar bölgesi": (
        "Fiyat bir süredir dar bir aralıkta gidip geliyor. Henüz yön seçmiş değil."
    ),
    "Trend devamı": (
        "Fiyat belirgin bir yönde ilerliyor ve göstergeler bu yönü destekliyor."
    ),
    "Trend içi geri çekilme": (
        "Ana yön korunuyor ama hareket şu an duraklamış durumda."
    ),
    "Tükenme denemesi": (
        "Mevcut hareket yorulma belirtisi gösteriyor. Bu bir dönüş işareti değil, sadece erken uyarı."
    ),
    "Mücadele / emilim bölgesi": (
        "Alıcı ve satıcı bu seviyede çekişiyor; işlem çok ama fiyat pek yol almıyor."
    ),
    "Yön arayışı / geçiş": (
        "Göstergeler birbirini tutmuyor; fiyat şu an net bir yön göstermiyor."
    ),
}


def _fmt(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return "—" if not math.isfinite(number) else f"{number:,.2f}"


def _participation_plain(rvol: float, in_squeeze: bool) -> str:
    if not math.isfinite(rvol):
        return "İşlem yoğunluğu hesaplanamadı."
    if rvol < 0.8:
        if in_squeeze:
            return "İşlem hacmi normalin altında, ama sıkışma dönemlerinde bu beklenen bir durum."
        return "İşlem hacmi normalin altında; yani harekete katılım zayıf."
    if rvol >= 1.5:
        return "İşlem hacmi normalin belirgin şekilde üzerinde; harekete katılım yüksek."
    return "İşlem hacmi normal seviyelerde."


def build_plain_summary(
    symbol: str,
    price: float,
    change_pct: float,
    setup_context: dict[str, Any],
    scenario: dict[str, Any],
    clarity: dict[str, Any],
    bar_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Raporun ana bulgusunu teknik terim kullanmadan anlatır."""
    setup = setup_context.get("setup", {})
    name = str(setup.get("name", ""))
    bias = str(setup.get("bias", ""))
    duration = setup_context.get("duration", {})
    participation = setup_context.get("participation_reading", {})
    rvol = participation.get("rvol_1")
    if rvol is None:
        rvol = math.nan
    in_squeeze = int(duration.get("squeeze_bars", 0)) >= 3 or "sıkışma" in name.casefold()

    sentences: list[str] = [
        f"{symbol} {_fmt(price)} seviyesinde, günü %{change_pct:+.2f} değişimle kapattı."
    ]
    sentences.append(SETUP_PLAIN.get(name, "Fiyatın durumu klasik bir kalıba tam oturmuyor."))

    squeeze_bars = int(duration.get("squeeze_bars", 0))
    if squeeze_bars >= 3:
        sentences.append(f"Bu dar aralık {squeeze_bars} işlem günüdür sürüyor.")

    plain_participation = _participation_plain(float(rvol), in_squeeze)
    sentences.append(plain_participation)

    def threshold_only(item: str) -> str:
        """Senaryo metninden yalnızca eşik ifadesini alır, teknik etiketi atar."""
        return item.split(":")[0].strip().casefold()

    upward = [item for item in scenario.get("strengthen", []) if "yukarı" in item.casefold()]
    downward = [item for item in scenario.get("strengthen", []) if "aşağı" in item.casefold()]
    if bias == "iki yönlü" and upward and downward:
        sentences.append(
            f"Yön iki eşikten biriyle belli olur: {threshold_only(upward[0])} olursa yukarı, "
            f"{threshold_only(downward[0])} olursa aşağı."
        )
    elif scenario.get("strengthen"):
        sentences.append(f"İzlenecek ilk eşik: {threshold_only(scenario['strengthen'][0])}.")

    clarity_state = str(clarity.get("state", ""))
    if clarity_state == "Düşük":
        sentences.append("Şu an göstergeler birbirini net biçimde doğrulamıyor; bekleyip görmek için sebep var.")
    elif clarity_state == "Orta":
        sentences.append("Bir eğilim var ama henüz kesinleşmiş değil.")
    elif clarity_state == "Yüksek":
        sentences.append("Göstergelerin büyük kısmı aynı şeyi söylüyor.")

    if bar_state and bar_state.get("is_live"):
        sentences.append("Not: gün henüz kapanmadı, bu rakamlar kapanışa kadar değişebilir.")

    sentences.append("Bu bir alım veya satım tavsiyesi değildir; yalnızca fiyatın mevcut durumunun özetidir.")
    return {
        "text": " ".join(sentences),
        "sentences": sentences,
        "method": "Teknik sınıflamaların gündelik dile birebir çevirisi; yeni bir iddia veya tahmin içermez.",
    }
