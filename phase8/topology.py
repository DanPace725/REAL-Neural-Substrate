from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Sequence

from .substrate import SUPPORTED_CONTEXTS, SUPPORTED_TRANSFORMS


def _edge_id(source_id: str, target_id: str) -> str:
    return f"{source_id}->{target_id}"


@dataclass
class MorphogenesisConfig:
    enabled: bool = False
    checkpoint_interval: int = 6
    max_events_per_checkpoint: int = 1
    max_dynamic_nodes: int = 4
    frontier_hop_limit: int = 2
    atp_surplus_threshold: float = 0.75
    surplus_window: int = 3
    contradiction_threshold: float = 0.55
    overload_threshold: float = 0.60
    energy_decay: float = 0.74
    growth_energy_threshold: float = 0.03
    prune_energy_threshold: float = -0.01
    apoptosis_energy_threshold: float = -0.03
    traffic_value_scale: float = 0.04
    dynamic_edge_upkeep: float = 0.008
    dynamic_node_upkeep: float = 0.012
    # Number of cycles after bud during which dynamic node upkeep is waived.
    # Prevents premature apoptosis during the slow-start learning window.
    growth_grace_ticks: int = 0
    # When > 0.0, allow growth proposals on source nodes when ingress_backlog
    # exceeds this fraction even without full ATP surplus.  This enables
    # pre-provisioning before sustained-pressure overload.
    anticipatory_growth_backlog_threshold: float = 0.0
    growth_queue_tolerance: int = 1
    growth_interrupt_urgency_threshold: float = 0.35
    edge_prune_ticks: int = 6
    isolation_ticks: int = 6
    probation_feedback_threshold: float = 0.18
    bud_edge_cost: float = 0.18
    bud_node_cost: float = 0.28
    prune_edge_cost: float = 0.05
    apoptosis_cost: float = 0.02
    seed_edge_support: float = 0.32
    seed_action_support: float = 0.24
    growth_route_novelty_bonus: float = 0.12
    growth_route_probationary_bonus: float = 0.10
    # When > 0.0, bud proposals are suppressed unless the node's
    # feedback_recent meets this threshold.  Prevents growth before the node
    # has demonstrated useful routing (positive feedback signal required).
    routing_feedback_gate: float = 0.0
    # When > 0.0, bud_edge and bud_node proposals are suppressed while a node's
    # effective_context_confidence is below this value AND a task packet is
    # present.  Prevents structural growth during the context-inference window.
    # Prune and apoptosis actions are never suppressed by this gate.
    context_resolution_growth_gate: float = 0.0


@dataclass
class NodeSpec:
    node_id: str
    position: int
    created_cycle: int = 0
    lineage_parent: str | None = None
    dynamic: bool = False
    probationary: bool = False
    probation_feedback_total: float = 0.0
    first_feedback_cycle: int | None = None
    surplus_streak: int = 0
    dormant_ticks: int = 0
    isolated_ticks: int = 0
    route_cost_total: float = 0.0
    maintenance_cost_total: float = 0.0
    growth_cost_total: float = 0.0
    feedback_total: float = 0.0
    route_cost_recent: float = 0.0
    maintenance_cost_recent: float = 0.0
    growth_cost_recent: float = 0.0
    feedback_recent: float = 0.0
    atp_ratio_ema: float = 1.0
    reward_ratio_ema: float = 0.0
    structural_upkeep_recent: float = 0.0
    net_energy_recent: float = 0.0
    value_recent: float = 0.0
    positive_energy_streak: int = 0
    negative_energy_streak: int = 0

    @property
    def lineage_depth(self) -> int:
        return 0 if self.lineage_parent is None else 1


@dataclass
class EdgeSpec:
    source_id: str
    target_id: str
    created_cycle: int = 0
    dynamic: bool = False
    last_used_cycle: int | None = None
    route_cost_total: float = 0.0
    maintenance_cost_total: float = 0.0
    feedback_total: float = 0.0
    route_cost_recent: float = 0.0
    maintenance_cost_recent: float = 0.0
    feedback_recent: float = 0.0
    traversal_count_total: int = 0
    traversal_recent: float = 0.0
    value_recent: float = 0.0
    negative_value_streak: int = 0

    @property
    def edge_id(self) -> str:
        return _edge_id(self.source_id, self.target_id)


@dataclass
class GrowthProposal:
    action: str
    node_id: str
    cycle: int
    score: float
    cost: float
    target_id: str | None = None
    slot: int | None = None
    reason: str = ""


@dataclass
class TopologyEvent:
    event_type: str
    cycle: int
    node_id: str
    target_id: str | None = None
    created_node_id: str | None = None
    detail: str = ""


@dataclass
class TopologyState:
    source_id: str
    sink_id: str
    node_specs: Dict[str, NodeSpec] = field(default_factory=dict)
    edge_specs: Dict[str, EdgeSpec] = field(default_factory=dict)
    initial_node_count: int = 0
    dynamic_node_counter: int = 0
    events: List[TopologyEvent] = field(default_factory=list)
    last_energy_refresh_cycle: int = -1

    @classmethod
    def from_graph(
        cls,
        adjacency: Dict[str, Sequence[str] | Iterable[str]],
        positions: Dict[str, int],
        *,
        source_id: str,
        sink_id: str,
    ) -> "TopologyState":
        node_specs = {
            node_id: NodeSpec(
                node_id=node_id,
                position=int(position),
                dynamic=False,
            )
            for node_id, position in positions.items()
        }
        edge_specs = {}
        for node_id, neighbors in adjacency.items():
            for neighbor_id in neighbors:
                edge = EdgeSpec(
                    source_id=node_id,
                    target_id=str(neighbor_id),
                    dynamic=False,
                )
                edge_specs[edge.edge_id] = edge
        return cls(
            source_id=source_id,
            sink_id=sink_id,
            node_specs=node_specs,
            edge_specs=edge_specs,
            initial_node_count=len(node_specs),
        )

    @classmethod
    def from_dict(cls, payload: dict | None) -> "TopologyState":
        if not payload:
            raise ValueError("Topology payload is required")
        state = cls(
            source_id=str(payload["source_id"]),
            sink_id=str(payload["sink_id"]),
            initial_node_count=int(payload.get("initial_node_count", 0)),
            dynamic_node_counter=int(payload.get("dynamic_node_counter", 0)),
        )
        state.node_specs = {
            node_id: NodeSpec(**node_payload)
            for node_id, node_payload in payload.get("node_specs", {}).items()
        }
        state.edge_specs = {
            edge_id: EdgeSpec(**edge_payload)
            for edge_id, edge_payload in payload.get("edge_specs", {}).items()
        }
        state.events = [
            TopologyEvent(**event_payload)
            for event_payload in payload.get("events", [])
        ]
        state.last_energy_refresh_cycle = int(payload.get("last_energy_refresh_cycle", -1))
        return state

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "sink_id": self.sink_id,
            "initial_node_count": self.initial_node_count,
            "dynamic_node_counter": self.dynamic_node_counter,
            "node_specs": {
                node_id: asdict(spec)
                for node_id, spec in self.node_specs.items()
            },
            "edge_specs": {
                edge_id: asdict(spec)
                for edge_id, spec in self.edge_specs.items()
            },
            "events": [asdict(event) for event in self.events],
            "last_energy_refresh_cycle": self.last_energy_refresh_cycle,
        }

    def positions_map(self) -> Dict[str, int]:
        return {
            node_id: spec.position
            for node_id, spec in self.node_specs.items()
        }

    def adjacency_map(self) -> Dict[str, tuple[str, ...]]:
        adjacency: Dict[str, List[str]] = {node_id: [] for node_id in self.node_specs}
        for edge in self.edge_specs.values():
            if edge.source_id not in adjacency or edge.target_id not in self.node_specs:
                continue
            adjacency[edge.source_id].append(edge.target_id)
        return {
            node_id: tuple(sorted(neighbors, key=lambda target_id: (self.node_specs[target_id].position, target_id)))
            for node_id, neighbors in adjacency.items()
        }

    def neighbors_of(self, node_id: str) -> tuple[str, ...]:
        return self.adjacency_map().get(node_id, ())

    def incoming_sources(self, node_id: str) -> List[str]:
        return sorted(
            edge.source_id
            for edge in self.edge_specs.values()
            if edge.target_id == node_id
        )

    def has_edge(self, source_id: str, target_id: str) -> bool:
        return _edge_id(source_id, target_id) in self.edge_specs

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        *,
        cycle: int,
        dynamic: bool = True,
    ) -> EdgeSpec:
        edge = EdgeSpec(
            source_id=source_id,
            target_id=target_id,
            created_cycle=cycle,
            dynamic=dynamic,
        )
        self.edge_specs[edge.edge_id] = edge
        return edge

    def remove_edge(self, source_id: str, target_id: str) -> bool:
        return self.edge_specs.pop(_edge_id(source_id, target_id), None) is not None

    def next_dynamic_node_id(self) -> str:
        while True:
            node_id = f"g{self.dynamic_node_counter}"
            self.dynamic_node_counter += 1
            if node_id not in self.node_specs:
                return node_id

    def add_node(
        self,
        *,
        position: int,
        cycle: int,
        parent_id: str | None = None,
        probationary: bool = True,
    ) -> NodeSpec:
        node_id = self.next_dynamic_node_id()
        spec = NodeSpec(
            node_id=node_id,
            position=position,
            created_cycle=cycle,
            lineage_parent=parent_id,
            dynamic=True,
            probationary=probationary,
        )
        self.node_specs[node_id] = spec
        return spec

    def remove_node(self, node_id: str) -> bool:
        if node_id not in self.node_specs:
            return False
        del self.node_specs[node_id]
        for edge_id in list(self.edge_specs.keys()):
            edge = self.edge_specs[edge_id]
            if edge.source_id == node_id or edge.target_id == node_id:
                del self.edge_specs[edge_id]
        return True

    def record_edge_use(self, source_id: str, target_id: str, cycle: int, cost: float = 0.0) -> None:
        edge = self.edge_specs.get(_edge_id(source_id, target_id))
        if edge is None:
            return
        edge.last_used_cycle = cycle
        edge.traversal_count_total += 1
        edge.traversal_recent += 1.0
        edge.route_cost_total += cost
        edge.route_cost_recent += cost
        spec = self.node_specs.get(source_id)
        if spec is None:
            return
        spec.route_cost_total += cost
        spec.route_cost_recent += cost

    def record_feedback(
        self,
        node_id: str,
        amount: float,
        cycle: int,
        config: MorphogenesisConfig,
        *,
        neighbor_id: str | None = None,
    ) -> None:
        spec = self.node_specs.get(node_id)
        if spec is None:
            return
        if amount > 0.0:
            spec.feedback_total += amount
            spec.feedback_recent += amount
            spec.probation_feedback_total += amount
            if spec.first_feedback_cycle is None:
                spec.first_feedback_cycle = cycle
            if spec.probationary and spec.probation_feedback_total >= config.probation_feedback_threshold:
                spec.probationary = False
            if neighbor_id is not None:
                edge = self.edge_specs.get(_edge_id(node_id, neighbor_id))
                if edge is not None:
                    edge.feedback_total += amount
                    edge.feedback_recent += amount

    def record_maintenance(
        self,
        node_id: str,
        spent: float,
        *,
        maintained_neighbors: Iterable[str] = (),
    ) -> None:
        spec = self.node_specs.get(node_id)
        if spec is None or spent <= 0.0:
            return
        spec.maintenance_cost_total += spent
        spec.maintenance_cost_recent += spent
        neighbors = sorted(set(str(neighbor_id) for neighbor_id in maintained_neighbors))
        if not neighbors:
            return
        share = spent / max(len(neighbors), 1)
        for neighbor_id in neighbors:
            edge = self.edge_specs.get(_edge_id(node_id, neighbor_id))
            if edge is None:
                continue
            edge.maintenance_cost_total += share
            edge.maintenance_cost_recent += share

    def record_growth_spend(self, node_id: str, cost: float) -> None:
        spec = self.node_specs.get(node_id)
        if spec is None or cost <= 0.0:
            return
        spec.growth_cost_total += cost
        spec.growth_cost_recent += cost

    def update_node_counters(
        self,
        *,
        node_states: Dict[str, object],
        adjacency: Dict[str, tuple[str, ...]],
        config: MorphogenesisConfig,
        cycle: int | None = None,
    ) -> None:
        if cycle is not None and self.last_energy_refresh_cycle == cycle:
            return
        decay = max(0.0, min(1.0, config.energy_decay))
        for edge in self.edge_specs.values():
            edge.route_cost_recent *= decay
            edge.maintenance_cost_recent *= decay
            edge.feedback_recent *= decay
            edge.traversal_recent *= decay
            upkeep = config.dynamic_edge_upkeep if edge.dynamic else 0.0
            edge.value_recent = (
                config.traffic_value_scale * edge.traversal_recent
                + edge.feedback_recent
                - edge.route_cost_recent
                - edge.maintenance_cost_recent
                - upkeep
            )
            if edge.dynamic and edge.value_recent < config.prune_energy_threshold:
                edge.negative_value_streak += 1
            else:
                edge.negative_value_streak = 0
        for node_id, spec in self.node_specs.items():
            if node_id == self.sink_id:
                continue
            state = node_states.get(node_id)
            if state is None:
                continue
            spec.route_cost_recent *= decay
            spec.maintenance_cost_recent *= decay
            spec.growth_cost_recent *= decay
            spec.feedback_recent *= decay
            atp = float(getattr(state, "atp", 0.0))
            max_atp = max(float(getattr(state, "max_atp", 1.0)), 1e-9)
            reward = float(getattr(state, "reward_buffer", 0.0))
            atp_ratio = atp / max_atp
            reward_ratio = reward / max_atp
            spec.atp_ratio_ema = decay * spec.atp_ratio_ema + (1.0 - decay) * atp_ratio
            spec.reward_ratio_ema = decay * spec.reward_ratio_ema + (1.0 - decay) * reward_ratio
            dynamic_outbound = sum(
                1
                for neighbor_id in adjacency.get(node_id, ())
                if self.edge_specs.get(_edge_id(node_id, neighbor_id)) is not None
                and self.edge_specs[_edge_id(node_id, neighbor_id)].dynamic
            )
            node_age = (cycle - spec.created_cycle) if cycle is not None else 0
            in_grace = (
                spec.dynamic
                and config.growth_grace_ticks > 0
                and node_age <= config.growth_grace_ticks
            )
            node_upkeep = 0.0 if in_grace else (config.dynamic_node_upkeep if spec.dynamic else 0.0)
            spec.structural_upkeep_recent = (
                decay * spec.structural_upkeep_recent
                + node_upkeep
                + dynamic_outbound * config.dynamic_edge_upkeep
            )
            outbound_value = sum(
                self.edge_specs[_edge_id(node_id, neighbor_id)].value_recent
                for neighbor_id in adjacency.get(node_id, ())
                if _edge_id(node_id, neighbor_id) in self.edge_specs
            )
            spec.net_energy_recent = (
                spec.feedback_recent
                - spec.route_cost_recent
                - spec.maintenance_cost_recent
                - spec.growth_cost_recent
                - spec.structural_upkeep_recent
            )
            spec.value_recent = (
                spec.net_energy_recent
                + 0.35 * spec.atp_ratio_ema
                + 0.20 * spec.reward_ratio_ema
                + 0.18 * outbound_value
            )
            if atp_ratio >= config.atp_surplus_threshold and spec.net_energy_recent >= config.growth_energy_threshold:
                spec.surplus_streak += 1
            else:
                spec.surplus_streak = 0
            if spec.net_energy_recent >= config.growth_energy_threshold:
                spec.positive_energy_streak += 1
            else:
                spec.positive_energy_streak = 0
            if spec.value_recent <= config.apoptosis_energy_threshold:
                spec.negative_energy_streak += 1
            else:
                spec.negative_energy_streak = 0
            if atp <= 1e-9:
                spec.dormant_ticks += 1
            else:
                spec.dormant_ticks = 0
            neighbors = adjacency.get(node_id, ())
            if not neighbors:
                spec.isolated_ticks += 1
            else:
                spec.isolated_ticks = 0
        if cycle is not None:
            self.last_energy_refresh_cycle = cycle

    def dynamic_node_count(self) -> int:
        return sum(1 for spec in self.node_specs.values() if spec.dynamic)

    def max_dynamic_nodes_reached(self, config: MorphogenesisConfig) -> bool:
        return self.dynamic_node_count() >= config.max_dynamic_nodes

    def candidate_targets(
        self,
        node_id: str,
        *,
        hop_limit: int = 2,
    ) -> List[str]:
        if node_id not in self.node_specs:
            return []
        current_position = self.node_specs[node_id].position
        current_neighbors = set(self.neighbors_of(node_id))
        candidates = []
        for target_id, spec in self.node_specs.items():
            if target_id == node_id or target_id == self.source_id:
                continue
            if target_id in current_neighbors:
                continue
            if spec.position <= current_position:
                continue
            if spec.position - current_position > hop_limit:
                continue
            candidates.append(target_id)
        return sorted(candidates, key=lambda target_id: (self.node_specs[target_id].position, target_id))

    def node_layer_slots(self, node_id: str) -> List[int]:
        if node_id not in self.node_specs:
            return []
        current_position = self.node_specs[node_id].position
        return [current_position + 1]

    def append_event(self, event: TopologyEvent) -> None:
        self.events.append(event)
        if len(self.events) > 200:
            self.events = self.events[-200:]


class TopologyManager:
    def __init__(self, config: MorphogenesisConfig | None = None) -> None:
        self.config = config or MorphogenesisConfig()

    def should_checkpoint(self, cycle: int) -> bool:
        return self.config.enabled and cycle > 0 and cycle % self.config.checkpoint_interval == 0

    def apply_checkpoint(self, system: "NativeSubstrateSystem", cycle: int) -> List[TopologyEvent]:
        if not self.config.enabled:
            return []
        system.environment.sync_topology()
        system.topology_state.update_node_counters(
            node_states=system.environment.node_states,
            adjacency=system.environment.adjacency,
            config=self.config,
            cycle=cycle,
        )
        proposals = list(system.environment.pending_growth_proposals)
        system.environment.pending_growth_proposals = []
        proposals.sort(key=lambda proposal: (proposal.score, -proposal.cost), reverse=True)
        applied: List[TopologyEvent] = []
        for proposal in proposals:
            if len(applied) >= self.config.max_events_per_checkpoint:
                break
            event = self._apply_proposal(system, proposal, cycle)
            if event is not None:
                applied.append(event)
                system.topology_state.append_event(event)
        applied.extend(self._auto_prune_edges(system, cycle))
        applied.extend(self._auto_apoptosis(system, cycle))
        if applied:
            system.environment.sync_topology()
        return applied

    def _apply_proposal(
        self,
        system: "NativeSubstrateSystem",
        proposal: GrowthProposal,
        cycle: int,
    ) -> TopologyEvent | None:
        if proposal.action.startswith("bud_edge:"):
            return self._apply_bud_edge(system, proposal, cycle)
        if proposal.action.startswith("bud_node:"):
            return self._apply_bud_node(system, proposal, cycle)
        if proposal.action.startswith("prune_edge:"):
            return self._apply_prune_edge(system, proposal, cycle)
        if proposal.action == "apoptosis_request":
            return self._apply_apoptosis_request(system, proposal, cycle)
        return None

    def _apply_bud_edge(
        self,
        system: "NativeSubstrateSystem",
        proposal: GrowthProposal,
        cycle: int,
    ) -> TopologyEvent | None:
        if proposal.target_id is None:
            return None
        if proposal.node_id not in system.topology_state.node_specs:
            return None
        if proposal.target_id not in system.topology_state.node_specs:
            return None
        source_pos = system.topology_state.node_specs[proposal.node_id].position
        target_pos = system.topology_state.node_specs[proposal.target_id].position
        if target_pos <= source_pos or target_pos - source_pos > self.config.frontier_hop_limit:
            return None
        if system.topology_state.has_edge(proposal.node_id, proposal.target_id):
            return None
        system.topology_state.add_edge(proposal.node_id, proposal.target_id, cycle=cycle, dynamic=True)
        system.environment.sync_topology()
        system.refresh_agent_neighbors(proposal.node_id)
        self._seed_growth_path(system, proposal.node_id, proposal.target_id)
        return TopologyEvent(
            event_type="bud_edge",
            cycle=cycle,
            node_id=proposal.node_id,
            target_id=proposal.target_id,
            detail=proposal.reason,
        )

    def _apply_bud_node(
        self,
        system: "NativeSubstrateSystem",
        proposal: GrowthProposal,
        cycle: int,
    ) -> TopologyEvent | None:
        if proposal.target_id is None or proposal.slot is None:
            return None
        if system.topology_state.max_dynamic_nodes_reached(self.config):
            return None
        if proposal.node_id not in system.topology_state.node_specs:
            return None
        if proposal.target_id not in system.topology_state.node_specs:
            return None
        source_pos = system.topology_state.node_specs[proposal.node_id].position
        target_pos = system.topology_state.node_specs[proposal.target_id].position
        if proposal.slot <= source_pos or proposal.slot >= target_pos:
            return None
        new_spec = system.topology_state.add_node(
            position=proposal.slot,
            cycle=cycle,
            parent_id=proposal.node_id,
            probationary=True,
        )
        system.topology_state.add_edge(proposal.node_id, new_spec.node_id, cycle=cycle, dynamic=True)
        system.topology_state.add_edge(new_spec.node_id, proposal.target_id, cycle=cycle, dynamic=True)
        system.environment.sync_topology()
        system.ensure_agent(new_spec.node_id, probationary=True)
        system.refresh_agent_neighbors(proposal.node_id)
        system.refresh_agent_neighbors(new_spec.node_id)
        self._seed_growth_path(system, proposal.node_id, new_spec.node_id)
        self._seed_growth_path(
            system,
            new_spec.node_id,
            proposal.target_id,
            template_node_id=proposal.node_id,
        )
        return TopologyEvent(
            event_type="bud_node",
            cycle=cycle,
            node_id=proposal.node_id,
            target_id=proposal.target_id,
            created_node_id=new_spec.node_id,
            detail=proposal.reason,
        )

    def _apply_prune_edge(
        self,
        system: "NativeSubstrateSystem",
        proposal: GrowthProposal,
        cycle: int,
    ) -> TopologyEvent | None:
        if proposal.target_id is None:
            return None
        neighbors = system.topology_state.neighbors_of(proposal.node_id)
        if proposal.target_id not in neighbors or len(neighbors) <= 1:
            return None
        edge = system.topology_state.edge_specs.get(_edge_id(proposal.node_id, proposal.target_id))
        if edge is None or not edge.dynamic:
            return None
        removed = system.topology_state.remove_edge(proposal.node_id, proposal.target_id)
        if not removed:
            return None
        system.environment.sync_topology()
        system.refresh_agent_neighbors(proposal.node_id)
        return TopologyEvent(
            event_type="prune_edge",
            cycle=cycle,
            node_id=proposal.node_id,
            target_id=proposal.target_id,
            detail=proposal.reason,
        )

    def _apply_apoptosis_request(
        self,
        system: "NativeSubstrateSystem",
        proposal: GrowthProposal,
        cycle: int,
    ) -> TopologyEvent | None:
        return self._remove_node_if_allowed(system, proposal.node_id, cycle, detail=proposal.reason)

    def _auto_prune_edges(self, system: "NativeSubstrateSystem", cycle: int) -> List[TopologyEvent]:
        events: List[TopologyEvent] = []
        for edge in list(system.topology_state.edge_specs.values()):
            if len(events) >= self.config.max_events_per_checkpoint:
                break
            if not edge.dynamic:
                continue
            if edge.source_id in (system.topology_state.sink_id,):
                continue
            neighbors = system.topology_state.neighbors_of(edge.source_id)
            if edge.target_id not in neighbors or len(neighbors) <= 1:
                continue
            if edge.last_used_cycle is None:
                idle_ticks = cycle - edge.created_cycle
            else:
                idle_ticks = cycle - edge.last_used_cycle
            if (
                edge.negative_value_streak < self.config.edge_prune_ticks
                and idle_ticks < self.config.edge_prune_ticks
            ):
                continue
            agent = system.agents.get(edge.source_id)
            if agent is None or edge.target_id not in agent.neighbor_ids:
                continue
            if (
                edge.value_recent > self.config.prune_energy_threshold
                or agent.substrate.support(edge.target_id) > agent.substrate.config.bistable_threshold
            ):
                continue
            proposal = GrowthProposal(
                action=f"prune_edge:{edge.target_id}",
                node_id=edge.source_id,
                target_id=edge.target_id,
                cycle=cycle,
                score=0.0,
                cost=0.0,
                reason="negative_edge_energy",
            )
            event = self._apply_prune_edge(system, proposal, cycle)
            if event is not None:
                events.append(event)
                system.topology_state.append_event(event)
        return events

    def _auto_apoptosis(self, system: "NativeSubstrateSystem", cycle: int) -> List[TopologyEvent]:
        events: List[TopologyEvent] = []
        for node_id, spec in list(system.topology_state.node_specs.items()):
            if not spec.dynamic:
                continue
            if len(events) >= self.config.max_events_per_checkpoint:
                break
            if (
                spec.negative_energy_streak < self.config.isolation_ticks
                and spec.dormant_ticks < self.config.isolation_ticks
                and spec.isolated_ticks < self.config.isolation_ticks
            ):
                continue
            event = self._remove_node_if_allowed(system, node_id, cycle, detail="auto_apoptosis")
            if event is not None:
                events.append(event)
                system.topology_state.append_event(event)
        return events

    def _remove_node_if_allowed(
        self,
        system: "NativeSubstrateSystem",
        node_id: str,
        cycle: int,
        *,
        detail: str,
    ) -> TopologyEvent | None:
        if node_id not in system.topology_state.node_specs:
            return None
        if node_id in (system.topology_state.source_id, system.topology_state.sink_id):
            return None
        spec = system.topology_state.node_specs[node_id]
        if system.environment.inboxes.get(node_id):
            return None
        if any(edge.startswith(f"{node_id}->") for pulse in system.environment.pending_feedback for edge in pulse.edge_path):
            return None
        agent = system.agents.get(node_id)
        if agent is not None and agent.substrate.active_neighbors() and spec.value_recent > self.config.apoptosis_energy_threshold:
            return None
        incoming_sources = system.topology_state.incoming_sources(node_id)
        removed = system.topology_state.remove_node(node_id)
        if not removed:
            return None
        system.environment.sync_topology()
        system.remove_agent(node_id)
        for source_id in incoming_sources:
            system.refresh_agent_neighbors(source_id)
        return TopologyEvent(
            event_type="apoptosis",
            cycle=cycle,
            node_id=node_id,
            detail=detail,
        )

    def _seed_growth_path(
        self,
        system: "NativeSubstrateSystem",
        source_id: str,
        target_id: str,
        *,
        template_node_id: str | None = None,
    ) -> None:
        source_agent = system.agents.get(source_id)
        if source_agent is None:
            return
        source_agent.substrate.seed_support((target_id,), value=self.config.seed_edge_support)

        transform_source_id = template_node_id or source_id
        for transform_name, context_bit, seeded_value in self._growth_transform_seeds(system, transform_source_id):
            source_agent.substrate.seed_action_support(
                target_id,
                transform_name,
                value=seeded_value,
                context_bit=context_bit,
            )

    def _growth_transform_seeds(
        self,
        system: "NativeSubstrateSystem",
        node_id: str,
    ) -> List[tuple[str, int | None, float]]:
        state = system.environment.node_states.get(node_id)
        if state is None:
            return [("identity", None, self.config.seed_action_support)]

        generic_scores = []
        context_scores = []
        for transform_name in SUPPORTED_TRANSFORMS:
            credit = float(state.transform_credit.get(transform_name, 0.0))
            debt = float(state.transform_debt.get(transform_name, 0.0))
            score = credit - 0.35 * debt
            generic_scores.append((score, transform_name))
            for context_bit in SUPPORTED_CONTEXTS:
                context_key = f"{transform_name}:context_{int(context_bit)}"
                context_credit = float(state.context_transform_credit.get(context_key, 0.0))
                context_debt = float(state.context_transform_debt.get(context_key, 0.0))
                context_score = context_credit - 0.30 * context_debt
                context_scores.append((context_score, transform_name, int(context_bit)))

        generic_scores.sort(reverse=True)
        context_scores.sort(reverse=True)
        seeds: List[tuple[str, int | None, float]] = []
        for score, transform_name in generic_scores[:2]:
            if score > 0.0:
                seeds.append(
                    (
                        transform_name,
                        None,
                        min(1.0, self.config.seed_action_support + 0.10 * min(score, 1.0)),
                    )
                )
        for score, transform_name, context_bit in context_scores[:2]:
            if score > 0.0:
                seeds.append(
                    (
                        transform_name,
                        context_bit,
                        min(1.0, self.config.seed_action_support + 0.12 * min(score, 1.0)),
                    )
                )
        if not seeds:
            seeds.append(("identity", None, self.config.seed_action_support))
        return seeds
