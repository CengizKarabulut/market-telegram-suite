from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LevelLifecycle(str, Enum):
    ACTIVE = "ACTIVE"
    TESTED = "TESTED"
    BROKEN_UP = "BROKEN_UP"
    BROKEN_DOWN = "BROKEN_DOWN"
    RECLAIMED = "RECLAIMED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"


class LevelClass(str, Enum):
    NEAR_TERM = "NEAR_TERM"
    SECONDARY = "SECONDARY"
    STRUCTURAL = "STRUCTURAL"


class ScenarioState(str, Enum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    INVALIDATED = "INVALIDATED"
    STALE = "STALE"


class EvidenceDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNCERTAINTY = "UNCERTAINTY"


@dataclass(frozen=True)
class Pivot:
    index: int
    timestamp: Any
    price: float
    kind: str  # HIGH | LOW
    degree: str = "minor"
    strength: float = 0.0
    prominence_atr: float = 0.0
    confirmed: bool = True


@dataclass(frozen=True)
class StructureEvent:
    kind: str  # BOS_UP | BOS_DOWN | CHOCH_UP | CHOCH_DOWN
    level: float
    pivot_index: int
    trigger_index: int
    trigger_price: float
    confirmed: bool = True


@dataclass
class TechnicalLevel:
    value: float
    source: str
    role: str
    lifecycle_state: LevelLifecycle = LevelLifecycle.ACTIVE
    zone_low: float | None = None
    zone_high: float | None = None
    direction: str = "NEUTRAL"
    distance_pct: float | None = None
    distance_atr: float | None = None
    age_bars: int | None = None
    tests: int = 0
    broken: bool = False
    reclaimed: bool = False
    level_class: LevelClass = LevelClass.SECONDARY
    priority: float = 0.0
    actionability: float = 0.0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WaveHypothesis:
    id: str
    timeframe: str
    degree: str
    pattern_type: str
    direction: str
    pivot_indices: list[int]
    active_wave: str
    confidence: float
    hard_rule_valid: bool
    soft_score: float
    invalidation_level: float | None
    target_zones: list[tuple[float, float]] = field(default_factory=list)
    alternate_rank: int = 0
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class MarketState:
    symbol: str
    timestamp: Any
    interval: str
    price: float
    change_pct: float = 0.0
    bar_state: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    wave_hypotheses: list[WaveHypothesis] = field(default_factory=list)
    levels: list[TechnicalLevel] = field(default_factory=list)
    regime: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    relative_strength: dict[str, Any] = field(default_factory=dict)
    multi_timeframe: dict[str, Any] = field(default_factory=dict)
    changes: list[str] = field(default_factory=list)
    confidence: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
