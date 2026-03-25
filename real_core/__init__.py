"""REAL Phase 4 core package."""

from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
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
from .lamination import HeuristicSliceRegulator, LaminatedController, LaminatedRunResult, LearningSliceRegulator
from .meta_agent import REALSliceRegulator, SliceSummaryObservationAdapter, PolicySelectionActionBackend, SliceAccuracyCoherenceModel, NAMED_POLICIES
from .interfaces import CarryoverFilter, SliceRegulator, SliceRunner

__all__ = [
    "ActionOutcome",
    "CycleEntry",
    "DimensionScores",
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
    "SliceSummary",
    "SubstrateSnapshot",
    "EpisodicMemory",
    "ConstraintPattern",
    "PatternRecognitionModel",
    "BasicConsolidationPipeline",
    "MemorySubstrate",
    "SubstrateConfig",
    "MemorySubstrateProtocol",
    "ConsolidationPipeline",
    "ContextualSelector",
    "DomainMemoryBinding",
    "ExpectationModel",
    "CarryoverFilter",
    "AnticipatorySelector",
    "RecognitionModel",
    "SliceRegulator",
    "SliceRunner",
    "CFARSelector",
    "SelectionMode",
    "TiltRegulatoryMesh",
    "SessionHistory",
    "SessionRecord",
    "SessionStateStore",
    "HeuristicSliceRegulator",
    "LaminatedController",
    "LaminatedRunResult",
    "LearningSliceRegulator",
    "ModeExperience",
    "REALSliceRegulator",
    "SliceSummaryObservationAdapter",
    "PolicySelectionActionBackend",
    "SliceAccuracyCoherenceModel",
    "NAMED_POLICIES",
]
