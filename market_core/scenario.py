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
