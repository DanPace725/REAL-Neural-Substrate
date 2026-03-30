# REAL Neural Substrate — Code Tour

_A walkthrough for people who want to understand how the system actually runs_

---

If you want the conceptual background first, read [`PLAIN_ENGLISH_OVERVIEW.md`](reports/PLAIN_ENGLISH_OVERVIEW.md). If you want the architectural philosophy, read [`architecture_notes.md`](summaries/architecture_notes.md). This document picks up from there and traces through the actual code.

---

## Table of Contents

1. [The Task Setup — CVT-1](#the-task-setup--cvt-1)
2. [Package Map](#package-map)
3. [Walking Through a Single Step](#walking-through-a-single-step)
4. [The REAL Loop in Code](#the-real-loop-in-code)
5. [Where Learning Lives](#where-learning-lives)
6. [Transfer and Carryover](#transfer-and-carryover)
7. [Morphogenesis](#morphogenesis)
8. [Running Experiments](#running-experiments)

---

## The Task Setup — CVT-1

The core experiment is called **CVT-1** (Context-Variable Transform, stage 1). It's the minimal case where useful behavior requires learning a hidden context.

A network of nodes receives packets of 4-bit vectors. The source node injects them; the sink node scores them. The correct transform to apply to each packet depends on a **context bit** — a signal not directly visible to most of the network. There are three task families (A, B, C) with partially overlapping transform mappings, designed to test both cold-start learning and transfer across tasks.

The four possible transforms are:
- `identity` — bits pass through unchanged
- `rotate_left_1` — shift bits one position left
- `xor_mask_1010` — XOR with mask 1010
- `xor_mask_0101` — XOR with mask 0101

The network must figure out — purely from local feedback — which edges to prefer, which transforms to apply, and (in the harder latent mode) what context it is probably operating in.

The scenario definitions live in `phase8/scenarios.py`. The topology builders there define how many nodes exist, how they connect, and what packet workload gets injected.

---

## Package Map

```
real_core/          domain-agnostic engine layer
  engine.py         RealCoreEngine — the main observe→consolidate loop
  interfaces.py     Protocol definitions binding real_core to any domain
  substrate.py      MemorySubstrate — two-layer fast/slow memory
  selector.py       CFARSelector — action selection strategy
  types.py          All shared dataclasses
  consolidation.py  BasicConsolidationPipeline — episodic retention
  recognition.py    PatternRecognitionModel
  lamination.py     LaminatedController — multi-slice execution
  meta_agent.py     REALSliceRegulator — slow-layer policy selector

phase8/             CVT-1 routing experiment layer
  environment.py    RoutingEnvironment + NativeSubstrateSystem
  node_agent.py     NodeAgent — wraps RealCoreEngine per node
  substrate.py      ConnectionSubstrate — edge-keyed substrate for Phase 8
  adapters.py       ObservationAdapter, ActionBackend, CoherenceModel
  selector.py       Phase8Selector — routing-aware selection
  consolidation.py  Phase8ConsolidationPipeline
  topology.py       TopologyManager — morphogenesis
  scenarios.py      Scenario + topology factory functions
  lamination.py     Phase8SliceRunner — slice adapter for CVT-1
  admission.py      AdmissionSubstrate — metabolic ingress gate

scripts/            Runnable experiment entrypoints
tests/              Test suite
docs/               Architecture notes, reports, traces
```

The design rule is strict: `real_core` must stay domain-agnostic. Everything routing-specific lives in `phase8`. The boundary between them is the `interfaces.py` protocol definitions.

---

## Walking Through a Single Step

Here is what happens when a single packet moves through the network.

### 1. Packet injection

`phase8/environment.py` — `NativeSubstrateSystem.inject_signal()`

A `SignalPacket` (`phase8/models.py`) is created and placed in the source node's inbox. It carries the raw 4-bit vector, a context bit (which may or may not be exposed, depending on mode), and a task ID.

The source node also has an `AdmissionSubstrate` (`phase8/admission.py`) that gates how fast new packets enter. If the source buffer is already backed up, admission support falls and ingress slows down — this is the metabolic ingress control.

### 2. The node observes its environment

`phase8/adapters.py` — `LocalNodeObservationAdapter.observe()`

Before each action, the node builds an observation dict from its current state:
- How full is its inbox?
- What is its ATP budget?
- Which neighbors are available?
- What is the context signal (if visible)?
- What does its substrate say about each edge/transform's support?

This dict is passed into the `RealCoreEngine` at the start of each cycle.

### 3. Recognition and prediction

`real_core/engine.py` — `RealCoreEngine.run_cycle()`

The engine runs the full loop:

```
observe → recognize → predict → select → execute → score → compare → consolidate
```

**Recognition** (`real_core/recognition.py`): the `PatternRecognitionModel` checks whether the current observation resembles any stored constraint patterns in the substrate. If it does, it returns a `RecognitionState` with a confidence score and matched patterns. This is local familiarity detection, not classification.

**Prediction** (`phase8/expectation.py`): the `Phase8ExpectationModel` anticipates what each available action would yield — expected delivery success, bit accuracy, routing efficiency. These are local predictions, not global plans.

### 4. Action selection

`phase8/selector.py` — `Phase8Selector.select()`

The selector weighs:
- Substrate support for each edge/transform (from `ConnectionSubstrate.use_cost()`)
- Recognition match bonus (if the current state resembles a known good pattern)
- Prediction delta bonus (if a specific action is anticipated to help)
- Context support (does the substrate have a learned preference for this transform in this context?)
- ATP budget (high-cost actions are deprioritized when budget is tight)

The `CFARSelector` in `real_core/selector.py` handles the base selection strategy. `Phase8Selector` extends it with routing-specific urgency and context-adaptation logic.

Early in training the selector mostly fluctuates (explores). As substrate support builds, it increasingly exploits known-good routes.

### 5. Action execution

`phase8/adapters.py` — `LocalNodeActionBackend.execute()`

Actions fall into a few families:
- `route:<neighbor_id>` — move the packet to a neighbor (no transform)
- `route_transform:<neighbor_id>:<transform_name>` — apply a named transform and route
- `rest` — do nothing, conserve ATP
- `maintain_edges` — invest in maintaining edge support
- `bud_edge:<neighbor_id>` / `bud_node:` — grow new connections (morphogenesis)
- `prune_edge:` / `apoptosis_request` — shrink

`route_with_transform()` in `phase8/environment.py` applies the transform, moves the packet, deducts ATP from the acting node, and records the hop.

### 6. Scoring (local coherence)

`phase8/adapters.py` — `LocalNodeCoherenceModel.score()`

After execution, six coherence dimensions are scored:
- `delivery_success` — are packets actually reaching the sink?
- `routing_efficiency` — ATP spent per delivered packet
- `bit_accuracy` — fraction of bits in delivered packets that matched the target
- `carryover_health` — is the substrate maintaining useful support?
- `growth_viability` — does the topology have room to grow if needed?
- `context_adaptation` — is the system tracking the right context?

These map to the general REAL dimensions (continuity, vitality, contextual_fit, differentiation, accountability, reflexivity) defined in `real_core/substrate.py`.

### 7. Feedback propagation

When a packet reaches the sink (`phase8/environment.py` — `deliver_packet()`), the environment generates a `FeedbackPulse` (`phase8/models.py`). The pulse carries the delivery amount and a `transform_path` recording which transforms were applied along the route.

The pulse travels **backwards** through the edge path using `FeedbackPulse.next_edge()`. Each node that receives it calls `NodeAgent.absorb_feedback()`, which calls `ConnectionSubstrate.record_feedback()` and `record_context_feedback()` to write the reward into the substrate.

This is the only "training signal" in the system. It is purely local and sequential — no node ever gets a signal that wasn't earned by a packet that passed through it.

### 8. Substrate update

`phase8/substrate.py` — `ConnectionSubstrate.record_feedback()`

The substrate maintains edge-keyed and context-action-keyed support values. When feedback arrives:
- The edge that routed the packet gains support
- The transform-context pair that was applied gains context credit
- Fast-layer values update immediately
- Slow-layer values update more gradually via `MemorySubstrate.tick()` in `real_core/substrate.py`

The slow layer has bistable dynamics: values below a threshold decay quickly; values above it decay slowly and are cheap to maintain. This means learned preferences become structurally durable without requiring constant reinforcement.

### 9. Consolidation

`phase8/consolidation.py` — `Phase8ConsolidationPipeline.consolidate()`

Periodically (when the inbox is quiet and ATP allows), the node consolidates its episodic history. High-coherence entries, high-delta entries, and near-threshold entries are retained as candidate attractors. Entries that reflect reliable context-action pairings are prioritized for carry-forward.

Consolidation produces a `SessionCarryover` package that can be loaded into a fresh session to warm-start from learned state.

---

## The REAL Loop in Code

The canonical entry point for a single node's execution is:

```python
# phase8/node_agent.py
class NodeAgent:
    def step(self):
        cycle = self.engine.run_cycle(self._cycle_count)
        self._cycle_count += 1
        ...
```

And inside `RealCoreEngine.run_cycle()` (`real_core/engine.py`):

```python
def run_cycle(self, cycle: int) -> CycleEntry:
    # 1. Observe
    state = self._observer.observe(cycle)

    # 2. Recognize
    recognition = self._recognize_state()

    # 3. Predict
    predictions = self._anticipate_actions()

    # 4. Select
    action, mode = self._selector.select_with_context(
        available, self._history, SelectionContext(...)
    )

    # 5. Execute
    outcome = self._action_backend.execute(action)

    # 6. Score
    dimensions = self._coherence.score()
    coherence = self._coherence.composite(dimensions)

    # 7. Compare (prediction error)
    prediction_errors = self._compare_predictions(outcome, predictions)

    # 8. Consolidate (episodic record)
    entry = CycleEntry(...)
    self._episodic.append(entry)

    return entry
```

The full consolidation pass (substrate promotion) is a separate operation triggered by `NodeAgent.step()` when conditions are right.

---

## Where Learning Lives

Learning in REAL is not a backward pass. It shows up in three places:

### Substrate support (`phase8/substrate.py`)

The `ConnectionSubstrate` holds a `MemorySubstrate` from `real_core/substrate.py`. Each edge has a support value in both fast and slow layers. When feedback arrives, `record_feedback()` writes to the fast layer. `tick()` propagates updates to the slow layer over time.

The slow layer's bistable threshold (configured in `SubstrateConfig`) is what makes learning durable. Once a support value crosses the threshold, it persists cheaply. Below the threshold, it decays away. This is the "structural rewriting" mechanism — there are no weight matrices, but there are substrate values that physically change the cost of future actions.

### Carryover packages (`real_core/types.py`, `real_core/consolidation.py`)

A `SessionCarryover` holds a `SubstrateSnapshot` (the slow-layer state) plus retained episodic entries. When loaded into a fresh `RealCoreEngine`, it seeds both the substrate (`MemorySubstrate.seed_support()`) and the episodic history. This is how transfer between tasks works — the "grooves" from task A reduce the cost of related actions in task B.

### Context support (`phase8/substrate.py`)

The substrate also tracks context-action pairs separately. `record_context_feedback()` writes to context-indexed support values. `get_context_support()` returns the resolved context state, which the selector uses to prefer context-consistent actions even before the context is explicitly confirmed. This is the mechanism behind latent context inference — the substrate accumulates a preference for one context based on which transform sequences have been rewarded.

---

## Transfer and Carryover

The core transfer experiment is Task A → Task B.

1. Train the system on task A (`compare_task_transfer.py` or the equivalent laminated scenario)
2. Export carryover: `NativeSubstrateSystem.export_carryover()` — serializes each node's substrate snapshot and retained episodic entries
3. Load into a fresh system facing task B: `NativeSubstrateSystem.load_carryover()`
4. Run task B and compare the learning curve against a cold start

The key insight is that tasks A and B share some transform-context pairings. The substrate support built up for those pairings transfers directly. The system doesn't need to rediscover routes that were already rewarded.

The **latent transfer advantage** observed in experiments is that hiding the context bit during training forces the substrate to build more general, context-agnostic routing preferences. When those preferences carry into task B (which has a different context bit distribution), they generalize better than preferences that were tightly coupled to a specific visible context value.

### Laminated execution

Long multi-slice runs use `phase8/lamination.py` — `Phase8SliceRunner`. Each "slice" is a bounded run of N cycles with a fixed ATP budget and packet workload. The `LaminatedController` in `real_core/lamination.py` orchestrates the slices, optionally applying regulatory signals between them (via `REALSliceRegulator` in `real_core/meta_agent.py`).

The meta-agent uses its own REAL loop to select policies (capability modes, budget multipliers, growth authorization) based on summary statistics from the previous slice. It is a REAL agent regulating REAL agents.

---

## Morphogenesis

When a node has surplus ATP and is struggling with differentiation or delivery, it can grow new edges or spawn new nodes. This is implemented in `phase8/topology.py`.

The `TopologyManager` handles proposals and applications:
- `propose_edge_bud()` — request a new edge to a neighbor
- `propose_node_bud()` — request a new intermediate node
- `apply_bud()` — actually instantiate it in the environment

`NodeAgent.refresh_neighbors()` is called after topology changes to rewire the node's action vocabulary. New nodes start in a probationary state — they must earn ATP through successful routing before they become full participants.

Morphogenesis is gated by the `MorphogenesisConfig` in `phase8/topology.py`. Growth only fires when ATP surplus exceeds a threshold AND the node detects either contradiction signals or overload signals. In practice, this means the system only grows where it is struggling — growth does not run unchecked.

---

## Running Experiments

### Quick smoke test

```bash
pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python -m scripts.run_phase8_demo --mode comparison --seed 13 --scenario cvt1_task_a_stage1
```

### Transfer experiment

```bash
python -m scripts.compare_task_transfer
```

Runs Task A cold, exports carryover, then runs Task B warm vs cold. Reports exact-match accuracy per condition.

### Latent vs visible context

```bash
python -m scripts.compare_latent_context
```

Compares training with the context bit exposed vs hidden. Key result: latent training achieves better transfer.

### Sequential transfer (A → B → C)

```bash
python -m scripts.compare_sequential_transfer
```

Tests whether learning C after B after A shows catastrophic forgetting. Key result: it doesn't.

### Large topology with morphogenesis

```bash
python -m scripts.compare_morphogenesis_large
```

Uses a 10-node, 36-packet topology. Reports whether growth happens, where, and whether it improves delivery.

### Occupancy harness (real sensor data)

```bash
python -m scripts.run_occupancy_real_v3 --mode fresh_session
python -m scripts.run_occupancy_real_v3 --mode persistent --seeds 3
```

See `docs/running_occupancy_v3.md` for full CLI documentation.

### Interpreting output

Each experiment prints per-condition accuracy and exact-match counts. The key numbers to watch:
- **Exact matches** — packets delivered with the correct transform applied, not just delivered
- **Context accuracy** — how often the system infers the right context, especially in latent mode
- **Growth events** — in morphogenesis runs, whether edge/node buds fired and how they correlated with accuracy gains

For deeper diagnostics, experiment manifests are written to `docs/experiment_outputs/` as JSON. The `scripts/analyze_experiment_output.py` script parses these.

---

## What To Read Next

- `real_core/engine.py` — the full REAL loop implementation
- `phase8/environment.py` — routing environment and `NativeSubstrateSystem`
- `phase8/substrate.py` — how edge support and context credit actually accumulate
- `docs/reports/INTERPRETABILITY.md` — how to read node-level and selector-level diagnostics
- `docs/reports/SYNTHESIS.md` — current experimental results and what they mean
- `docs/traces/INDEX.md` — implementation history, searchable by keyword and file
