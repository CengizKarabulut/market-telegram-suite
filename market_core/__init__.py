"""Market Analysis Engine V3/V4 shared core.

Bu paket chart_bot ve technical_bot tarafından ortak kullanılacak yeni çekirdeğin
başlangıç noktasıdır. Yeni tam analiz katmanları production akışına alınana kadar
mevcut uygulamalar değiştirilmez.
"""

from .company_classification import CompanyClassification, classify_company
from .corporate_events import (
    CorporateEvent,
    build_corporate_event_timeline,
    classify_corporate_event,
    corporate_event_from_mapping,
)
from .engine import build_market_state
from .equity_report import (
    EQUITY_REPORT_SCHEMA,
    build_equity_report_contract,
    format_equity_report_preview,
)
from .external_evidence import (
    MALevelEvidence,
    ScanSignal,
    ma_level_from_mapping,
    ma_level_to_technical_level,
    ma_levels_for_interval,
    normalize_timeframe,
    scan_signal_from_mapping,
)
from .fundamental_metrics import MetricResult, build_fundamental_metrics
from .fundamental_models import (
    FinancialSnapshot,
    PointInTimeSelection,
    SectorType,
    StatementType,
)
from .fundamental_period import (
    PeriodComparative,
    build_current_period_fundamental_view,
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
from .peer_benchmarks import (
    PeerObservation,
    build_hierarchical_peer_benchmark,
    build_peer_benchmark,
)
from .peer_metric_adapter import peer_metrics_from_states
from .point_in_time import select_financial_snapshot
from .regime import build_regime
from .relative_strength import build_relative_strength
from .report import build_report_contract, format_telegram_preview, interval_label
from .sector_profiles import SectorMetricRule, SectorProfile, profile_for_sector
from .serialization import market_state_dict, market_state_json, report_json, to_primitive
from .technical_changes import build_technical_changes
from .technical_features import build_technical_features
from .tradingview_peers import (
    TRADINGVIEW_FIELDS,
    observations_from_tradingview_frame,
    tradingview_classification_from_frame,
)
from .ttm import TTMResult, assemble_ttm
from .valuation import ValuationState, build_daily_valuation

__all__ = [
    "CompanyClassification",
    "CorporateEvent",
    "EQUITY_REPORT_SCHEMA",
    "Evidence",
    "EvidenceDirection",
    "FinancialSnapshot",
    "LevelClass",
    "LevelLifecycle",
    "MALevelEvidence",
    "MarketState",
    "MetricResult",
    "PeerObservation",
    "PeriodComparative",
    "Pivot",
    "PointInTimeSelection",
    "ScanSignal",
    "ScenarioState",
    "SectorMetricRule",
    "SectorProfile",
    "SectorType",
    "StatementType",
    "StructureEvent",
    "TRADINGVIEW_FIELDS",
    "TTMResult",
    "TechnicalLevel",
    "ValuationState",
    "WaveHypothesis",
    "assemble_ttm",
    "build_corporate_event_timeline",
    "build_current_period_fundamental_view",
    "build_daily_valuation",
    "build_equity_report_contract",
    "build_fundamental_metrics",
    "build_hierarchical_peer_benchmark",
    "build_market_state",
    "build_multi_timeframe",
    "build_peer_benchmark",
    "build_regime",
    "build_relative_strength",
    "build_report_contract",
    "build_technical_changes",
    "build_technical_features",
    "classify_company",
    "classify_corporate_event",
    "corporate_event_from_mapping",
    "format_equity_report_preview",
    "format_telegram_preview",
    "interval_label",
    "ma_level_from_mapping",
    "ma_level_to_technical_level",
    "ma_levels_for_interval",
    "market_state_dict",
    "market_state_json",
    "normalize_timeframe",
    "observations_from_tradingview_frame",
    "peer_metrics_from_states",
    "profile_for_sector",
    "report_json",
    "scan_signal_from_mapping",
    "select_financial_snapshot",
    "to_primitive",
    "tradingview_classification_from_frame",
]
