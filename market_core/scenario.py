from __future__ import annotations

from dataclasses import dataclass

from .models import LevelLifecycle, ScenarioState, TechnicalLevel


@dataclass
class ScenarioCondition:
    id: str
    side: str  # UP | DOWN | NEUTRAL
    trigger_type: str
    level: float | None
    zone: tuple[float, float] | None
    state: ScenarioState
    confirmation_rule: str
    invalidation_rule: str
    source: str
    priority: float = 0.0


def state_for_level(level: TechnicalLevel, price: float, side: str) -> ScenarioState:
    """Bir seviyenin henüz beklenen koşul mu, yoksa zaten gerçekleşmiş mi olduğunu ayırır."""
    if level.lifecycle_state in {LevelLifecycle.STALE, LevelLifecycle.INVALIDATED}:
        return ScenarioState.STALE
    if side == "DOWN":
        if price < level.value or level.lifecycle_state == LevelLifecycle.BROKEN_DOWN:
            return ScenarioState.CONFIRMED
        return ScenarioState.PENDING
    if side == "UP":
        if price > level.value or level.lifecycle_state == LevelLifecycle.BROKEN_UP:
            return ScenarioState.CONFIRMED
        return ScenarioState.PENDING
    return ScenarioState.PENDING


def condition_from_level(level: TechnicalLevel, price: float, side: str) -> ScenarioCondition:
    state = state_for_level(level, price, side)
    verb = "üzerinde" if side == "UP" else "altında"
    return ScenarioCondition(
        id=f"{level.source}:{level.value:.8f}:{side}",
        side=side,
        trigger_type="CLOSE_ACCEPTANCE",
        level=level.value,
        zone=(level.zone_low, level.zone_high) if level.zone_low is not None and level.zone_high is not None else None,
        state=state,
        confirmation_rule=f"{level.value:.2f} {verb} kapanış ve kabul",
        invalidation_rule="Karşı yönde yeniden kabul",
        source=level.source,
        priority=level.priority,
    )


def _same_trigger(left: ScenarioCondition, right: ScenarioCondition, tolerance: float) -> bool:
    if left.side != right.side or left.trigger_type != right.trigger_type:
        return False
    if left.level is not None and right.level is not None:
        return abs(left.level - right.level) <= tolerance
    if left.zone is not None and right.zone is not None:
        return (
            abs(left.zone[0] - right.zone[0]) <= tolerance
            and abs(left.zone[1] - right.zone[1]) <= tolerance
        )
    return False


def deduplicate_conditions(
    conditions: list[ScenarioCondition],
    *,
    tolerance: float = 1e-6,
) -> list[ScenarioCondition]:
    """Aynı fiyat koşulunu üreten confluence kaynaklarını tek senaryoda toplar.

    Bir swing low ile Elliott invalidation aynı fiyata denk gelirse Telegram'da
    aynı cümle iki kez gösterilmez. En yüksek öncelikli koşul temsilci kalır;
    kaynak alanı audit için birleşik tutulur.
    """
    ordered = sorted(conditions, key=lambda item: item.priority, reverse=True)
    unique: list[ScenarioCondition] = []
    for condition in ordered:
        duplicate = next(
            (item for item in unique if _same_trigger(item, condition, tolerance)),
            None,
        )
        if duplicate is None:
            unique.append(condition)
            continue
        sources = sorted(set(duplicate.source.split("+") + condition.source.split("+")))
        duplicate.source = "+".join(source for source in sources if source)
        duplicate.id = f"CONFLUENCE:{duplicate.side}:{duplicate.level if duplicate.level is not None else duplicate.zone}"
        duplicate.priority = max(duplicate.priority, condition.priority)
    return unique


def pending_conditions(conditions: list[ScenarioCondition]) -> list[ScenarioCondition]:
    """Sunum katmanına yalnız gerçekten gelecekte beklenen koşulları verir."""
    return [item for item in conditions if item.state == ScenarioState.PENDING]


def assert_no_completed_condition_is_pending(conditions: list[ScenarioCondition], price: float) -> None:
    """ZGYO sınıfı mantık hatalarını erken yakalayan invariant."""
    for item in conditions:
        if item.state != ScenarioState.PENDING or item.level is None:
            continue
        if item.side == "DOWN" and price < item.level:
            raise AssertionError(f"Gerçekleşmiş aşağı koşul pending olamaz: fiyat {price} < seviye {item.level}")
        if item.side == "UP" and price > item.level:
            raise AssertionError(f"Gerçekleşmiş yukarı koşul pending olamaz: fiyat {price} > seviye {item.level}")
