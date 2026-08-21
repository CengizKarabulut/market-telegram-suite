"""Gorunumler: gostergeleri odakli karelere ayirir.

On gostergeyi tek bir grafige yigmak yerine, her biri 2-4 katman tasiyan
ayri kareler uretiriz. Boylece Bollinger'i incelerken MACD gurultusu,
momentuma bakarken bulut karmasasi ekrani mesgul etmez.

Her gorunum ayni sembol ve ayni bar araligindan cikar; tek veri cekimi ve
tek hesaplama turuyla hepsi uretilir (bkz. pipeline.build_views).

`keys` alani cizim sirasidir: once fiyat uzerine binen katmanlar, sonra alt
paneller. Hangi hesaplarin gerektigini plotspec.compute_keys_for cozer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .plotspec import compute_keys_for


@dataclass(frozen=True)
class View:
    key: str
    title: str
    keys: tuple[str, ...]
    note: str
    price_height: float = 3.0

    @property
    def compute_keys(self) -> tuple[str, ...]:
        return compute_keys_for(self.keys)


VIEWS: tuple[View, ...] = (
    View(
        key="bollinger_macd",
        title="Bollinger · Momentum · Hacim",
        keys=("bbands", "macd", "smi", "obv", "candles"),
        note="Bollinger 20/2 · MACD 12/26/9 · SMI 10/3/3 · OBV SMA14+BB2",
        price_height=3.4,
    ),
    View(
        key="ichimoku_rsi",
        title="Ichimoku · Momentum · Volatilite",
        keys=("ichimoku", "rsi", "cci", "atr", "candles"),
        note="Ichimoku 9/26/52/26 · RSI 14/SMA14 · CCI 20/SMA14 · ATR RMA14",
        price_height=3.4,
    ),
    View(
        key="sar_vwap",
        title="SAR · VWAP · Yön Gücü",
        keys=("sar", "vwap", "stochrsi", "adx", "candles"),
        note="Parabolic SAR · VWAP bantları · Stoch RSI · ADX/DMI 14",
        price_height=3.4,
    ),
    View(
        key="supertrend_fisher",
        title="Supertrend · Para Akışı · Momentum",
        keys=("supertrend", "fisher", "cmf", "momentum", "candles"),
        note="Supertrend 10/3 · Fisher 9 · CMF 20 · Momentum 10",
        price_height=3.4,
    ),
    View(
        key="klasik",
        title="Klasik",
        keys=("ma", "rsi", "bbpanel", "volume"),
        note="EMA 20/50 · RSI · Bollinger %B · Hacim",
        price_height=3.2,
    ),
    View(
        key="trend",
        title="Trend takip",
        keys=("supertrend", "macd", "atr", "obv"),
        note="Supertrend · MACD · ATR · OBV",
        price_height=3.2,
    ),
    View(
        key="kanal",
        title="Bulut ve kanal",
        keys=("ichimoku", "stochrsi", "kcpos", "vwapdev"),
        note="Ichimoku · Stoch RSI · Keltner konumu · VWAP sapması",
        price_height=3.2,
    ),
    View(
        key="kirilim",
        title="Kırılım ve dönüş",
        keys=("sar", "cci", "dcpos", "rvol"),
        note="Parabolic SAR · CCI · Donchian konumu · Bağıl hacim",
        price_height=3.2,
    ),
    View(
        key="profil",
        title="Hacim profili",
        keys=("vprofile", "willr", "bbwidth", "obv"),
        note="Volume Profile · Williams %R · Bant genişliği · OBV",
        price_height=2.8,
    ),
    View(
        key="tumu",
        title="Genel bakış",
        keys=("ma", "bbands", "supertrend", "ichimoku", "vwap",
              "volume", "rsi", "macd", "stochrsi", "adx"),
        note="On göstergenin tamamı tek karede",
        price_height=3.4,
    ),
)

#: Izgara olarak gonderilen dort kare
GRID_SET: tuple[str, ...] = (
    "bollinger_macd", "ichimoku_rsi", "sar_vwap", "supertrend_fisher"
)

VIEWS_BY_KEY: dict[str, View] = {v.key: v for v in VIEWS}

#: Telegram'a gonderilen varsayilan set
DEFAULT_SET: tuple[str, ...] = GRID_SET


def resolve_views(spec: str) -> tuple[View, ...]:
    """'all', 'set', virgullu liste veya tek anahtar cozer."""
    value = spec.strip().lower()
    if value in {"all", "hepsi"}:
        return VIEWS
    if value in {"set", "seri", "grid", "izgara"}:
        return tuple(VIEWS_BY_KEY[k] for k in DEFAULT_SET)
    keys = [k.strip() for k in value.split(",") if k.strip()]
    unknown = [k for k in keys if k not in VIEWS_BY_KEY]
    if unknown:
        raise KeyError(
            f"Bilinmeyen gorunum: {', '.join(unknown)}. "
            f"Gecerli: {', '.join(VIEWS_BY_KEY)} (ya da 'all' / 'set')"
        )
    return tuple(VIEWS_BY_KEY[k] for k in keys)
