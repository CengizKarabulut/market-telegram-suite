"""Market Analysis Engine V3/V4 shared core.

Bu paket chart_bot ve technical_bot tarafından ortak kullanılacak yeni çekirdeğin
başlangıç noktasıdır. Yeni tam analiz katmanları production akışına alınana kadar
mevcut uygulamalar değiştirilmez.
"""

from .engine import build_market_state
from .external_evidence import (
    MALevelEvidence,
    ScanSignal,
    ma_level_from_mapping,
    ma_level_to_technical_level,
    ma_levels_for_interval,
    normalize_timeframe,
    scan_signal_from_mapping,
)
from .fundamental_metrics import (
    MetricResult,
    build_fundamental_metrics,
)
from .fundamental_models import (
    FinancialSnapshot,
    PointInTimeSelection,
    SectorType,
    StatementType,
)
from .models import (
    Evidence,
    EvidenceDirection,
    LevelClass,
    LevelLifecycle,
    MarketState,
    Pivot,
    ScenarioState,
    StructureEvent,
    TechnicalLevel,
    WaveHypothesis,
)
from .multi_timeframe import build_multi_timeframe
from .point_in_time import select_financial_snapshot
from .regime import build_regime
from .relative_strength import build_relative_strength
from .report import build_report_contract, format_telegram_preview, interval_label
from .serialization import market_state_dict, market_state_json, report_json, to_primitive
from .technical_changes import build_technical_changes
from .technical_features import build_technical_features
from .ttm import TTMResult, assemble_ttm

__all__ = [
    "Evidence",
    "EvidenceDirection",
    "FinancialSnapshot",
    "LevelClass",
    "LevelLifecycle",
    "MALevelEvidence",
    "MarketState",
    "MetricResult",
    "Pivot",
    "PointInTimeSelection",
    "ScanSignal",
    "ScenarioState",
    "SectorType",
    "StatementType",
    "StructureEvent",
    "TTMResult",
    "TechnicalLevel",
    "WaveHypothesis",
    "assemble_ttm",
    "build_fundamental_metrics",
    "build_market_state",
    "build_multi_timeframe",
    "build_regime",
    "build_relative_strength",
    "build_report_contract",
    "build_technical_changes",
    "build_technical_features",
    "format_telegram_preview",
    "interval_label",
    "ma_level_from_mapping",
    "ma_level_to_technical_level",
    "ma_levels_for_interval",
    "market_state_dict",
    "market_state_json",
    "normalize_timeframe",
    "report_json",
    "scan_signal_from_mapping",
    "select_financial_snapshot",
    "to_primitive",
]
