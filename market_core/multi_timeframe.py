from __future__ import annotations

from typing import Any


def build_multi_timeframe(current_interval: str, states: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Harici/üst zaman dilimi özetlerinden uyum ve ayrışma üretir.

    Bu modül veri indirmez. Chart/technical bot aynı canonical motorla farklı
    interval state'lerini ürettikten sonra bu fonksiyona yalnız özetleri verir.
    """
    states = dict(states or {})
    if not states:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "alignment": 0.0,
            "direction": "UNCERTAINTY",
            "reason": "Ek zaman dilimi state'i sağlanmadı.",
            "intervals": {},
        }

    votes: list[int] = []
    normalized: dict[str, dict[str, Any]] = {}
    for interval, payload in states.items():
        if interval == current_interval:
            continue
        bias = str(payload.get("bias") or payload.get("structure_bias") or payload.get("direction") or "TRANSITION").upper()
        clarity = float(payload.get("clarity", 1.0) or 0.0)
        vote = 1 if bias in {"BULLISH", "UP"} else -1 if bias in {"BEARISH", "DOWN"} else 0
        if clarity < 0.3:
            vote = 0
        votes.append(vote)
        normalized[interval] = {"bias": bias, "clarity": clarity, "vote": vote}

    if not votes:
        return {
            "available": False,
            "state": "UNAVAILABLE",
            "alignment": 0.0,
            "direction": "UNCERTAINTY",
            "reason": "Karşılaştırılabilir farklı interval yok.",
            "intervals": normalized,
        }

    directional = [vote for vote in votes if vote != 0]
    if not directional:
        state = "MIXED_OR_NEUTRAL"
        direction = "UNCERTAINTY"
        alignment = 0.0
    else:
        net = sum(directional)
        alignment = abs(net) / len(directional)
        if alignment >= 0.67:
            direction = "BULLISH" if net > 0 else "BEARISH"
            state = "ALIGNED"
        else:
            direction = "UNCERTAINTY"
            state = "DIVERGENT"

    return {
        "available": True,
        "state": state,
        "alignment": alignment,
        "direction": direction,
        "reason": "Zaman dilimi uyumu yönlü kanıt, ayrışma ise belirsizlik olarak değerlendirilir.",
        "intervals": normalized,
    }
