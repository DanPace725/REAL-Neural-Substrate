"""REAL Phase 4 core package."""

from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
    LocalPrediction,
    MemoryActionSpec,
    PredictionError,
    RecognitionMatch,
    RecognitionState,
    SelectionContext,
    SessionCarryover,
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
    "SelectionContext",
    "RealCoreEngine",
    "SessionCarryover",
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
    "AnticipatorySelector",
    "RecognitionModel",
    "CFARSelector",
    "SelectionMode",
    "TiltRegulatoryMesh",
    "SessionHistory",
    "SessionRecord",
    "SessionStateStore",
]
