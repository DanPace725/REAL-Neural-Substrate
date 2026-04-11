"""REAL Phase 4 core package."""

from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    ForecastError,
    ForecastOutput,
    GCOStatus,
    LocalPrediction,
    MemoryActionSpec,
    ModeExperience,
    PredictionError,
    RecognitionMatch,
    RecognitionState,
    RegulatorySignal,
    SelectionContext,
    SessionCarryover,
    SettlementDecision,
    SliceExecutionPlan,
    SliceSummary,
    SubstrateSnapshot,
)
from .engine import RealCoreEngine
from .episodic import EpisodicMemory
from .interfaces import (
    ConsolidationPipeline,
    ContextualSelector,
    DomainMemoryBinding,
    ExpectationModel,
    ForecastReadout,
    MemorySubstrateProtocol,
    RecognitionModel,
)
from .selector import AnticipatorySelector, CFARSelector, SelectionMode
from .mesh import TiltRegulatoryMesh
from .patterns import ConstraintPattern
from .recognition import PatternRecognitionModel
from .consolidation import BasicConsolidationPipeline
from .session import SessionHistory, SessionRecord
from .session_state import SessionStateStore
from .substrate import MemorySubstrate, SubstrateConfig
from .regulatory_substrate import (
    RegulatoryComposition,
    RegulatoryLatentState,
    RegulatoryObservation,
    RegulatoryPrimitive,
    RegulatoryPrimitiveState,
    RegulatorySubstrate,
)
from .lamination import (
    GradientSliceRegulator,
    HeuristicSliceRegulator,
    LaminatedController,
    LaminatedRunResult,
    LearningSliceRegulator,
)
from .meta_agent import REALSliceRegulator, SliceSummaryObservationAdapter, PolicySelectionActionBackend, SliceAccuracyCoherenceModel, NAMED_POLICIES
from .world_model import (
    REALWorldModel,
    WORLD_MODEL_ASSISTANCE_MODES,
    WORLD_MODEL_HYPOTHESES,
    WorldModelObservationAdapter,
)
from .interfaces import AdaptiveSliceRunner, CarryoverFilter, SliceRegulator, SliceRunner

__all__ = [
    "ActionOutcome",
    "CycleEntry",
    "DimensionScores",
    "ForecastError",
    "ForecastOutput",
    "GCOStatus",
    "LocalPrediction",
    "MemoryActionSpec",
    "PredictionError",
    "RecognitionMatch",
    "RecognitionState",
    "RegulatorySignal",
    "SelectionContext",
    "RealCoreEngine",
    "SessionCarryover",
    "SettlementDecision",
    "SliceExecutionPlan",
    "SliceSummary",
    "SubstrateSnapshot",
    "EpisodicMemory",
    "ConstraintPattern",
    "PatternRecognitionModel",
    "BasicConsolidationPipeline",
    "MemorySubstrate",
    "SubstrateConfig",
    "RegulatoryPrimitive",
    "RegulatoryPrimitiveState",
    "RegulatoryObservation",
    "RegulatoryComposition",
    "RegulatoryLatentState",
    "RegulatorySubstrate",
    "MemorySubstrateProtocol",
    "ConsolidationPipeline",
    "ContextualSelector",
    "DomainMemoryBinding",
    "ExpectationModel",
    "ForecastReadout",
    "CarryoverFilter",
    "AnticipatorySelector",
    "RecognitionModel",
    "SliceRegulator",
    "SliceRunner",
    "AdaptiveSliceRunner",
    "CFARSelector",
    "SelectionMode",
    "TiltRegulatoryMesh",
    "SessionHistory",
    "SessionRecord",
    "SessionStateStore",
    "HeuristicSliceRegulator",
    "GradientSliceRegulator",
    "LaminatedController",
    "LaminatedRunResult",
    "LearningSliceRegulator",
    "ModeExperience",
    "REALSliceRegulator",
    "SliceSummaryObservationAdapter",
    "PolicySelectionActionBackend",
    "SliceAccuracyCoherenceModel",
    "NAMED_POLICIES",
    "REALWorldModel",
    "WORLD_MODEL_ASSISTANCE_MODES",
    "WorldModelObservationAdapter",
    "WORLD_MODEL_HYPOTHESES",
]
