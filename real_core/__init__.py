"""REAL Phase 4 core package."""

from .types import (
    ActionOutcome,
    CycleEntry,
    DimensionScores,
    GCOStatus,
    MemoryActionSpec,
    SessionCarryover,
    SubstrateSnapshot,
)
from .engine import RealCoreEngine
from .episodic import EpisodicMemory
from .interfaces import ConsolidationPipeline, DomainMemoryBinding, MemorySubstrateProtocol
from .selector import CFARSelector, SelectionMode
from .mesh import TiltRegulatoryMesh
from .patterns import ConstraintPattern
from .consolidation import BasicConsolidationPipeline
from .session import SessionHistory, SessionRecord
from .session_state import SessionStateStore
from .substrate import MemorySubstrate, SubstrateConfig

__all__ = [
    "ActionOutcome",
    "CycleEntry",
    "DimensionScores",
    "GCOStatus",
    "MemoryActionSpec",
    "RealCoreEngine",
    "SessionCarryover",
    "SubstrateSnapshot",
    "EpisodicMemory",
    "ConstraintPattern",
    "BasicConsolidationPipeline",
    "MemorySubstrate",
    "SubstrateConfig",
    "MemorySubstrateProtocol",
    "ConsolidationPipeline",
    "DomainMemoryBinding",
    "CFARSelector",
    "SelectionMode",
    "TiltRegulatoryMesh",
    "SessionHistory",
    "SessionRecord",
    "SessionStateStore",
]
