"""Cell pool: a persistent registry of REAL sub-agents (cells) that the
organizer actively maintains, allocates resources to, and coordinates.

This is the distinction between REAL *being* cells (structural composition)
and REAL *having* cells (active orchestration of a living workforce).

Each cell:
  - Is a specialized REAL agent with its own coherence model
  - Persists across activations (maintains state between runs)
  - Receives metabolic budget from the pool
  - Can signal other cells through the shared signal bus
  - Can be grown (spawned) or pruned (killed) based on usefulness

The pool itself is not a REAL agent — it's infrastructure. The organizer
(which IS a REAL agent) interacts with the pool through actions like
`activate:<cell>`, `feed:<cell>`, `prune:<cell>`, and `grow:<role>`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .environment import TraceEnvironment


# ---------------------------------------------------------------------------
# Cell lifecycle
# ---------------------------------------------------------------------------

class CellState(Enum):
    """Lifecycle state of a cell in the pool."""
    DORMANT = "dormant"      # exists but not active, minimal cost
    ACTIVE = "active"        # currently running or ready to run
    EXHAUSTED = "exhausted"  # ran out of budget, needs feeding
    PRUNED = "pruned"        # marked for removal


# ---------------------------------------------------------------------------
# Cell roles — what a cell knows how to do
# ---------------------------------------------------------------------------

class CellRole(Enum):
    """The functional specialization of a cell."""
    SURVEYOR = "surveyor"    # batch similarity analysis, cluster discovery
    REFINER = "refiner"      # structural improvement, outlier detection
    READER = "reader"        # deep reading of traces, feature extraction
    LINKER = "linker"        # cross-group relationship discovery


# ---------------------------------------------------------------------------
# Signal bus — inter-cell communication
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """A message from one cell to another (or broadcast)."""
    source: str              # cell_id of sender
    target: str              # cell_id of receiver, or "*" for broadcast
    signal_type: str         # "need_data", "cluster_ready", "outlier_found", etc.
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


class SignalBus:
    """Shared communication channel between cells.

    Cells post signals; other cells consume them. Signals persist until
    consumed or expired (max age = 50 cycles).
    """

    MAX_AGE = 50

    def __init__(self) -> None:
        self._signals: List[Signal] = []
        self._cycle: int = 0

    def post(self, signal: Signal) -> None:
        signal.timestamp = float(self._cycle)
        self._signals.append(signal)

    def consume(self, cell_id: str, signal_type: str | None = None) -> List[Signal]:
        """Get and remove signals addressed to this cell (or broadcast)."""
        matched = []
        remaining = []
        for s in self._signals:
            if (s.target == cell_id or s.target == "*") and \
               (signal_type is None or s.signal_type == signal_type):
                matched.append(s)
            else:
                remaining.append(s)
        self._signals = remaining
        return matched

    def peek(self, cell_id: str, signal_type: str | None = None) -> List[Signal]:
        """Look at signals without consuming them."""
        return [
            s for s in self._signals
            if (s.target == cell_id or s.target == "*")
            and (signal_type is None or s.signal_type == signal_type)
        ]

    def tick(self, cycle: int) -> None:
        """Advance the bus clock and expire old signals."""
        self._cycle = cycle
        cutoff = cycle - self.MAX_AGE
        self._signals = [s for s in self._signals if s.timestamp >= cutoff]

    @property
    def pending_count(self) -> int:
        return len(self._signals)


# ---------------------------------------------------------------------------
# Cell — a persistent sub-agent with state
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    """A living sub-agent in the pool.

    Unlike the fire-and-forget surveyor/refiner, a Cell persists between
    activations. It remembers what it learned, accumulates state, and can
    be re-activated with new budget to continue where it left off.
    """

    cell_id: str
    role: CellRole
    state: CellState = CellState.DORMANT

    # Metabolic budget
    budget_total: float = 0.0        # lifetime budget allocated
    budget_remaining: float = 0.0    # current available budget
    budget_efficiency: float = 0.0   # coherence gained per budget spent

    # Performance tracking
    activations: int = 0
    total_cycles: int = 0
    best_coherence: float = 0.0
    last_coherence: float = 0.0
    contribution_score: float = 0.0  # how much this cell helped the organizer

    # Persistent state — survives across activations
    # Each role stores its own data structure here
    persistent_state: Dict[str, Any] = field(default_factory=dict)

    # Signals this cell wants to send after its run
    outbox: List[Signal] = field(default_factory=list)

    # Birth/death metadata
    born_at_cycle: int = 0
    last_active_cycle: int = 0
    pruned_at_cycle: int | None = None

    @property
    def age(self) -> int:
        """Cycles since birth (approximate, based on last_active_cycle)."""
        return self.last_active_cycle - self.born_at_cycle

    @property
    def is_alive(self) -> bool:
        return self.state != CellState.PRUNED

    @property
    def is_activatable(self) -> bool:
        return self.state in (CellState.DORMANT, CellState.EXHAUSTED)

    def feed(self, budget: float) -> None:
        """Add metabolic budget to this cell."""
        self.budget_remaining += budget
        self.budget_total += budget
        if self.state == CellState.EXHAUSTED:
            self.state = CellState.DORMANT

    def record_activation(self, cycles_used: int, coherence: float, cycle: int) -> None:
        """Record the results of an activation."""
        self.activations += 1
        self.total_cycles += cycles_used
        self.last_coherence = coherence
        self.best_coherence = max(self.best_coherence, coherence)
        self.last_active_cycle = cycle

        # Update efficiency: coherence per unit budget
        budget_spent = self.budget_total - self.budget_remaining
        if budget_spent > 0:
            self.budget_efficiency = self.best_coherence / budget_spent

        # If budget is depleted, mark exhausted
        if self.budget_remaining <= 0.01:
            self.state = CellState.EXHAUSTED
        else:
            self.state = CellState.DORMANT

    def prune(self, cycle: int) -> None:
        """Mark this cell for removal."""
        self.state = CellState.PRUNED
        self.pruned_at_cycle = cycle


# ---------------------------------------------------------------------------
# Cell Pool — the living workforce
# ---------------------------------------------------------------------------

class CellPool:
    """Manages a pool of persistent REAL sub-agents.

    The pool is infrastructure, not a REAL agent itself. The organizer
    interacts with it through explicit actions. The pool handles:
      - Cell lifecycle (create, activate, feed, prune)
      - Budget allocation across cells
      - Inter-cell signaling via the SignalBus
      - Performance tracking and contribution scoring

    The pool exposes numeric observations that the organizer can perceive,
    letting it make allostatic decisions about which cells to nurture.
    """

    # Pool-level metabolic constants
    DORMANT_COST = 0.001         # per-cycle cost of keeping a dormant cell alive
    DEFAULT_CELL_BUDGET = 3.0    # initial budget when growing a new cell
    MIN_CONTRIBUTION = 0.01      # cells below this get pruning pressure
    MAX_CELLS = 8                # don't grow beyond this

    def __init__(self, environment: TraceEnvironment) -> None:
        self.environment = environment
        self.cells: Dict[str, Cell] = {}
        self.bus = SignalBus()
        self._cycle: int = 0
        self._total_budget_allocated: float = 0.0

        # Role → factory function mapping (set by the organizer)
        self._role_runners: Dict[CellRole, Callable] = {}

    # ------------------------------------------------------------------
    # Pool-level observations (for the organizer to perceive)
    # ------------------------------------------------------------------

    def observe(self) -> Dict[str, float]:
        """Numeric snapshot of pool state for the organizer's observation."""
        alive = [c for c in self.cells.values() if c.is_alive]
        active = [c for c in alive if c.state == CellState.ACTIVE]
        exhausted = [c for c in alive if c.state == CellState.EXHAUSTED]
        dormant = [c for c in alive if c.state == CellState.DORMANT]

        # Role coverage: what fraction of roles have living cells
        roles_covered = len(set(c.role for c in alive))
        role_coverage = roles_covered / len(CellRole)

        # Mean efficiency across alive cells
        efficiencies = [c.budget_efficiency for c in alive if c.budget_efficiency > 0]
        mean_efficiency = sum(efficiencies) / len(efficiencies) if efficiencies else 0.0

        # Mean contribution
        contributions = [c.contribution_score for c in alive]
        mean_contribution = sum(contributions) / len(contributions) if contributions else 0.0

        # Budget health: what fraction of total budget is still available
        total_remaining = sum(c.budget_remaining for c in alive)
        budget_health = total_remaining / max(0.1, self._total_budget_allocated)

        return {
            "pool_size": len(alive) / self.MAX_CELLS,
            "active_cells": len(active) / max(1, len(alive)),
            "exhausted_cells": len(exhausted) / max(1, len(alive)),
            "role_coverage": role_coverage,
            "mean_efficiency": min(1.0, mean_efficiency),
            "mean_contribution": min(1.0, mean_contribution),
            "budget_health": min(1.0, budget_health),
            "pending_signals": min(1.0, self.bus.pending_count / 10.0),
        }

    # ------------------------------------------------------------------
    # Cell lifecycle operations
    # ------------------------------------------------------------------

    def grow(self, role: CellRole, budget: float | None = None) -> Cell | None:
        """Grow a new cell with the given role.

        Returns the new cell, or None if the pool is full.
        """
        alive = [c for c in self.cells.values() if c.is_alive]
        if len(alive) >= self.MAX_CELLS:
            return None

        budget = budget or self.DEFAULT_CELL_BUDGET
        cell_id = f"{role.value}-{len(self.cells)}"

        cell = Cell(
            cell_id=cell_id,
            role=role,
            state=CellState.DORMANT,
            budget_remaining=budget,
            budget_total=budget,
            born_at_cycle=self._cycle,
        )
        self.cells[cell_id] = cell
        self._total_budget_allocated += budget
        return cell

    def activate(self, cell_id: str) -> Dict[str, Any]:
        """Activate a cell — run its REAL loop with its current budget.

        The cell runs until stable or budget-exhausted, then returns
        to dormant/exhausted state with updated persistent_state.

        Returns a summary of what happened.
        """
        cell = self.cells.get(cell_id)
        if cell is None or not cell.is_activatable:
            return {"success": False, "reason": f"cell {cell_id} not activatable"}

        runner = self._role_runners.get(cell.role)
        if runner is None:
            return {"success": False, "reason": f"no runner for role {cell.role.value}"}

        cell.state = CellState.ACTIVE

        # Deliver any pending signals to this cell
        incoming = self.bus.consume(cell_id)

        # Run the cell's REAL loop
        t0 = time.perf_counter()
        result = runner(
            env=self.environment,
            cell=cell,
            incoming_signals=incoming,
        )
        elapsed = time.perf_counter() - t0

        # Record results
        cell.budget_remaining -= elapsed
        cell.record_activation(
            cycles_used=result.get("cycles_used", 0),
            coherence=result.get("final_coherence", 0.0),
            cycle=self._cycle,
        )

        # Post any outgoing signals
        for signal in cell.outbox:
            self.bus.post(signal)
        cell.outbox.clear()

        return {
            "success": True,
            "cell_id": cell_id,
            "role": cell.role.value,
            "cycles_used": result.get("cycles_used", 0),
            "coherence": result.get("final_coherence", 0.0),
            "activation_count": cell.activations,
            "budget_remaining": cell.budget_remaining,
            **{k: v for k, v in result.items() if k not in ("cycles_used", "final_coherence")},
        }

    def feed(self, cell_id: str, budget: float) -> bool:
        """Add budget to a cell."""
        cell = self.cells.get(cell_id)
        if cell is None or not cell.is_alive:
            return False
        cell.feed(budget)
        self._total_budget_allocated += budget
        return True

    def prune(self, cell_id: str) -> bool:
        """Kill a cell, freeing its resources."""
        cell = self.cells.get(cell_id)
        if cell is None or not cell.is_alive:
            return False
        cell.prune(self._cycle)
        return True

    def auto_prune(self) -> List[str]:
        """Prune underperforming cells automatically.

        Cells are pruned if:
          - They've been activated 3+ times with near-zero contribution
          - They've been exhausted for 30+ cycles without being fed
        """
        pruned = []
        for cell in list(self.cells.values()):
            if not cell.is_alive:
                continue

            # Chronic underperformance
            if cell.activations >= 3 and cell.contribution_score < self.MIN_CONTRIBUTION:
                cell.prune(self._cycle)
                pruned.append(cell.cell_id)
                continue

            # Exhausted and neglected
            if cell.state == CellState.EXHAUSTED:
                cycles_exhausted = self._cycle - cell.last_active_cycle
                if cycles_exhausted > 30:
                    cell.prune(self._cycle)
                    pruned.append(cell.cell_id)

        return pruned

    # ------------------------------------------------------------------
    # Contribution scoring — how much does each cell help the organizer?
    # ------------------------------------------------------------------

    def update_contributions(self, organizer_coherence: float, organizer_delta: float) -> None:
        """Update cell contribution scores based on the organizer's coherence.

        Called after each organizer cycle. Cells that were recently active
        get credit (positive or negative) for the organizer's coherence change.
        """
        for cell in self.cells.values():
            if not cell.is_alive:
                continue

            # Cells active in the last 5 cycles get credit
            recency = self._cycle - cell.last_active_cycle
            if recency <= 5 and cell.activations > 0:
                # Credit proportional to recency (more recent = more credit)
                weight = max(0.0, 1.0 - recency / 5.0)
                cell.contribution_score = (
                    0.85 * cell.contribution_score +
                    0.15 * weight * organizer_delta
                )

    # ------------------------------------------------------------------
    # Pool tick — maintenance
    # ------------------------------------------------------------------

    def tick(self, cycle: int) -> Dict[str, Any]:
        """Per-cycle pool maintenance.

        Called once per organizer cycle. Handles:
          - Signal bus expiry
          - Dormant cell cost
          - Auto-pruning check (every 20 cycles)
        """
        self._cycle = cycle
        self.bus.tick(cycle)

        # Dormant cells cost a tiny amount to maintain
        for cell in self.cells.values():
            if cell.state == CellState.DORMANT and cell.budget_remaining > 0:
                cell.budget_remaining -= self.DORMANT_COST
                if cell.budget_remaining <= 0:
                    cell.state = CellState.EXHAUSTED

        # Periodic auto-prune
        pruned = []
        if cycle % 20 == 0:
            pruned = self.auto_prune()

        return {
            "cycle": cycle,
            "alive": sum(1 for c in self.cells.values() if c.is_alive),
            "pruned_this_tick": pruned,
        }

    # ------------------------------------------------------------------
    # Registration — connect role runners
    # ------------------------------------------------------------------

    def register_runner(self, role: CellRole, runner: Callable) -> None:
        """Register a function that runs a cell's REAL loop.

        The runner signature is:
            runner(env: TraceEnvironment, cell: Cell, incoming_signals: List[Signal])
                -> Dict[str, Any]

        It must return at minimum {"cycles_used": int, "final_coherence": float}.
        The runner can read/write cell.persistent_state and append to cell.outbox.
        """
        self._role_runners[role] = runner

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def cells_by_role(self, role: CellRole) -> List[Cell]:
        return [c for c in self.cells.values() if c.role == role and c.is_alive]

    def best_cell(self, role: CellRole | None = None) -> Cell | None:
        """Return the highest-contribution alive cell, optionally filtered by role."""
        candidates = [
            c for c in self.cells.values()
            if c.is_alive and (role is None or c.role == role)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.contribution_score)

    def needs_feeding(self) -> List[Cell]:
        """Return exhausted cells that have contributed positively."""
        return [
            c for c in self.cells.values()
            if c.state == CellState.EXHAUSTED and c.contribution_score > 0
        ]

    def growth_candidates(self) -> List[CellRole]:
        """Return roles that have registered runners and no living cells."""
        active_roles = set(c.role for c in self.cells.values() if c.is_alive)
        return [
            r for r in CellRole
            if r not in active_roles and r in self._role_runners
        ]
