from __future__ import annotations

import math
from dataclasses import asdict

from .models import Pivot, WaveHypothesis


def _fib_ratio(value: float, reference: float) -> float:
    return abs(value) / abs(reference) if reference else math.nan


def _near(value: float, targets: tuple[float, ...], tolerance: float = 0.18) -> tuple[bool, float | None]:
    if not math.isfinite(value):
        return False, None
    closest = min(targets, key=lambda target: abs(value - target))
    return abs(value - closest) <= tolerance, closest


def _alternating(pivots: list[Pivot]) -> bool:
    return all(left.kind != right.kind for left, right in zip(pivots, pivots[1:]))


def _impulse_hard_rules(points: list[Pivot], direction: str) -> tuple[bool, list[str]]:
    """Standart 1-2-3-4-5 impulsunun temel Elliott kurallarını doğrular."""
    if len(points) != 6 or not _alternating(points):
        return False, ["Altı dönüş noktası ve HIGH/LOW alternasyonu gerekli."]
    p0, p1, p2, p3, p4, p5 = [item.price for item in points]
    warnings: list[str] = []
    if direction == "UP":
        if not (p1 > p0 and p2 > p0 and p3 > p1 and p4 > p1 and p5 > p3):
            warnings.append("Yukarı impuls fiyat sıralaması sağlanmıyor.")
        wave1, wave3, wave5 = p1 - p0, p3 - p2, p5 - p4
        if p2 <= p0:
            warnings.append("Wave 2, Wave 1 başlangıcını geçti.")
        if p4 <= p1:
            warnings.append("Wave 4, standart impulsta Wave 1 alanına girdi.")
    else:
        if not (p1 < p0 and p2 < p0 and p3 < p1 and p4 < p1 and p5 < p3):
            warnings.append("Aşağı impuls fiyat sıralaması sağlanmıyor.")
        wave1, wave3, wave5 = p0 - p1, p2 - p3, p4 - p5
        if p2 >= p0:
            warnings.append("Wave 2, Wave 1 başlangıcını geçti.")
        if p4 >= p1:
            warnings.append("Wave 4, standart impulsta Wave 1 alanına girdi.")
    if min(wave1, wave3, wave5) == wave3:
        warnings.append("Wave 3, 1-3-5 arasında en kısa dalga olamaz.")
    return not warnings, warnings


def _impulse_soft_score(points: list[Pivot], direction: str) -> tuple[float, list[str]]:
    p0, p1, p2, p3, p4, p5 = [item.price for item in points]
    if direction == "UP":
        w1, w2, w3, w4, w5 = p1 - p0, p1 - p2, p3 - p2, p3 - p4, p5 - p4
    else:
        w1, w2, w3, w4, w5 = p0 - p1, p2 - p1, p2 - p3, p4 - p3, p4 - p5
    score = 0.0
    reasons: list[str] = []
    r2 = _fib_ratio(w2, w1)
    hit, target = _near(r2, (0.382, 0.5, 0.618, 0.786), tolerance=0.16)
    if hit:
        score += 0.22
        reasons.append(f"Wave 2 retracement oranı {r2:.2f}, Fibonacci {target:.3f} çevresinde.")
    r3 = _fib_ratio(w3, w1)
    hit, target = _near(r3, (1.0, 1.272, 1.618, 2.0, 2.618), tolerance=0.24)
    if hit:
        score += 0.26
        reasons.append(f"Wave 3 / Wave 1 oranı {r3:.2f}, extension {target:.3f} çevresinde.")
    r4 = _fib_ratio(w4, w3)
    hit, target = _near(r4, (0.236, 0.382, 0.5), tolerance=0.14)
    if hit:
        score += 0.18
        reasons.append(f"Wave 4 retracement oranı {r4:.2f}, Fibonacci {target:.3f} çevresinde.")
    r5 = _fib_ratio(w5, w1)
    hit, target = _near(r5, (0.618, 1.0, 1.272, 1.618), tolerance=0.22)
    if hit:
        score += 0.18
        reasons.append(f"Wave 5 / Wave 1 oranı {r5:.2f}, Fibonacci {target:.3f} çevresinde.")
    duration1 = max(points[1].index - points[0].index, 1)
    duration3 = max(points[3].index - points[2].index, 1)
    duration5 = max(points[5].index - points[4].index, 1)
    if max(duration1, duration3, duration5) / min(duration1, duration3, duration5) <= 4:
        score += 0.08
        reasons.append("İmpuls dalga süreleri aşırı dengesiz değil.")
    if points[2].degree != points[4].degree:
        score += 0.08
        reasons.append("Wave 2 ve Wave 4 düzeltmeleri derece bakımından farklı; alternation için zayıf destek.")
    return min(score, 1.0), reasons


def _target_zone(points: list[Pivot], direction: str) -> tuple[float, float]:
    p0, p1, _, _, p4, _ = [item.price for item in points]
    wave1 = abs(p1 - p0)
    if direction == "UP":
        low = p4 + wave1 * 0.618
        high = p4 + wave1 * 1.0
    else:
        high = p4 - wave1 * 0.618
        low = p4 - wave1 * 1.0
    return (min(low, high), max(low, high))


def impulse_candidates(
    pivots: list[Pivot],
    timeframe: str = "1d",
    max_candidates: int = 4,
) -> list[WaveHypothesis]:
    candidates: list[WaveHypothesis] = []
    if len(pivots) < 6:
        return candidates
    windows = [pivots[start : start + 6] for start in range(max(0, len(pivots) - 12), len(pivots) - 5)]
    for points in windows:
        if not _alternating(points):
            continue
        direction = "UP" if points[1].price > points[0].price else "DOWN"
        hard_valid, warnings = _impulse_hard_rules(points, direction)
        if not hard_valid:
            continue
        soft_score, reasons = _impulse_soft_score(points, direction)
        recency = 1.0 / (1.0 + max(pivots[-1].index - points[-1].index, 0) / 10.0)
        degree_bonus = sum(item.degree == "intermediate" for item in points) / 6 * 0.08
        confidence = min(0.45 + soft_score * 0.45 + recency * 0.08 + degree_bonus, 0.99)
        hypothesis = WaveHypothesis(
            id=f"impulse-{points[0].index}-{points[-1].index}-{direction.lower()}",
            timeframe=timeframe,
            degree=max((item.degree for item in points), key=("micro", "minor", "intermediate").index),
            pattern_type="IMPULSE_12345",
            direction=direction,
            pivot_indices=[item.index for item in points],
            active_wave="IMPULSE_COMPLETE",
            confidence=confidence,
            hard_rule_valid=True,
            soft_score=soft_score,
            invalidation_level=points[0].price,
            target_zones=[],
            reasons=reasons + ["Wave 5 teyitli pivotla tamamlandığı için bu sayım aktif hedef üretmez."],
            warnings=warnings,
        )
        candidates.append(hypothesis)
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    for rank, item in enumerate(candidates[:max_candidates], start=1):
        item.alternate_rank = rank
    return candidates[:max_candidates]


def abc_candidates(pivots: list[Pivot], timeframe: str = "1d", max_candidates: int = 4) -> list[WaveHypothesis]:
    results: list[WaveHypothesis] = []
    if len(pivots) < 4:
        return results
    for start in range(max(0, len(pivots) - 10), len(pivots) - 3):
        points = pivots[start : start + 4]
        if not _alternating(points):
            continue
        p0, pa, pb, pc = [item.price for item in points]
        direction = "DOWN" if pa < p0 else "UP"
        a = abs(pa - p0)
        b = abs(pb - pa)
        c = abs(pc - pb)
        if not all(value > 0 for value in (a, b, c)):
            continue
        b_ratio = b / a
        c_ratio = c / a
        zigzag = b_ratio <= 0.786
        flat = 0.8 <= b_ratio <= 1.25
        if not (zigzag or flat):
            continue
        pattern = "ABC_ZIGZAG" if zigzag else "ABC_FLAT"
        reasons = [f"B/A oranı {b_ratio:.2f}.", f"C/A oranı {c_ratio:.2f}."]
        fib_bonus = 0.0
        hit, target = _near(c_ratio, (0.618, 1.0, 1.272, 1.618), tolerance=0.22)
        if hit:
            fib_bonus = 0.25
            reasons.append(f"C/A oranı Fibonacci {target:.3f} çevresinde.")
        confidence = min(0.45 + fib_bonus + (0.15 if zigzag else 0.10), 0.90)
        results.append(
            WaveHypothesis(
                id=f"abc-{points[0].index}-{points[-1].index}-{pattern.lower()}",
                timeframe=timeframe,
                degree=max((item.degree for item in points), key=("micro", "minor", "intermediate").index),
                pattern_type=pattern,
                direction=direction,
                pivot_indices=[item.index for item in points],
                active_wave="ABC_COMPLETE",
                confidence=confidence,
                hard_rule_valid=True,
                soft_score=fib_bonus,
                invalidation_level=p0,
                target_zones=[],
                reasons=reasons + ["C pivotu teyitli olduğundan sayım tamamlanmış yapı bağlamıdır."],
            )
        )
    results.sort(key=lambda item: item.confidence, reverse=True)
    for rank, item in enumerate(results[:max_candidates], start=1):
        item.alternate_rank = rank
    return results[:max_candidates]


def build_wave_hypotheses(pivots: list[Pivot], timeframe: str = "1d", max_total: int = 5) -> list[WaveHypothesis]:
    candidates = impulse_candidates(pivots, timeframe=timeframe) + abc_candidates(pivots, timeframe=timeframe)
    candidates.sort(key=lambda item: item.confidence, reverse=True)
    for rank, item in enumerate(candidates[:max_total], start=1):
        item.alternate_rank = rank
    return candidates[:max_total]


def hypothesis_as_dict(hypothesis: WaveHypothesis) -> dict:
    return asdict(hypothesis)
