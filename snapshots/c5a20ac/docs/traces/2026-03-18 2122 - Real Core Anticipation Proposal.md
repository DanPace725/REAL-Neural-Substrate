# 2026-03-18 2122 - Real Core Anticipation Proposal

Author: GPT-5 Codex

## Purpose

This document proposes a clean `real_core` generalization update so REAL can treat memory as anticipatory structure, not only retrospective residue.

The motivating distinction is:

- current REAL memory mostly biases future action through accumulated experience
- desired REAL memory should support both:
  - recognition of recurring problem shapes
  - prediction of likely local outcomes before acting

This proposal is meant to preserve the repo's non-negotiables:

- no global gradient path
- local knowledge only
- metabolic costs remain real constraints
- learning writes into structure
- `real_core` stays domain-agnostic

## Problem Statement

The current generalized REAL loop in [engine.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/engine.py) is effectively:

- observe
- select
- execute
- score
- consolidate

That loop supports:

- retrospective evaluation via post-action coherence
- local memory bias through substrate and episodic traces
- historical action preference through mean delta and cost

It does **not** make expectation or prediction a first-class concept in the core.

The evidence is structural:

- [interfaces.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/interfaces.py) has observation, action, coherence, selection, substrate, and memory-binding protocols, but no prediction interface
- [types.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/types.py) records `state_before`, `state_after`, `dimensions`, `coherence`, and `delta`, but not expected outcome or prediction error
- [selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/selector.py) ranks actions using historical delta and cost, not expected local consequence

Phase 8 has added local anticipation-like features, such as:

- `source_sequence_transform_hint_*`
- `effective_context_confidence`
- anticipatory growth backlog thresholds

but those are domain-local features in [environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py) and [selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py), not a generalized REAL capability.

## Thesis

REAL should generalize memory as **anticipatory structure**.

That means memory should do two jobs:

1. `recognition`
   Detect that the current local state resembles prior situations.

2. `prediction`
   Estimate what is likely to happen next if a given action is taken.

The generalized architecture should therefore support local prediction and local prediction error, not only post hoc action evaluation.

## Proposed Generalized Loop

Update the conceptual REAL loop from:

- perceive
- select
- execute
- score
- consolidate

to:

- sense
- recognize
- predict
- select
- execute
- compare
- consolidate

Definitions:

- `sense`: capture the current local state
- `recognize`: match current local state to episodic/substrate-supported prior situations
- `predict`: estimate likely local outcome for candidate actions, including confidence and uncertainty
- `select`: choose action using both historical and predicted consequence
- `execute`: act in the environment
- `compare`: measure actual outcome against expected outcome, producing local prediction error
- `consolidate`: write recurring useful predictions and recurring prediction errors into structure

## Architectural Principle

Prediction in REAL should be:

- local
- optional
- action-conditioned
- confidence-bearing
- metabolically relevant

Prediction should **not** be:

- a global oracle
- a centralized planner
- a monolithic world model

## Minimal Core Additions

### 1. Add Generalized Prediction Types

Extend [types.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/types.py) with domain-agnostic predictive records.

Suggested additions:

```python
@dataclass
class LocalPrediction:
    action: str
    expected_state: Dict[str, Any] = field(default_factory=dict)
    expected_dimensions: DimensionScores = field(default_factory=dict)
    expected_coherence: float | None = None
    expected_delta: float | None = None
    confidence: float = 0.0
    uncertainty: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionError:
    action: str
    confidence: float = 0.0
    expected_coherence: float | None = None
    actual_coherence: float | None = None
    coherence_error: float | None = None
    expected_delta: float | None = None
    actual_delta: float | None = None
    delta_error: float | None = None
    dimension_error: DimensionScores = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Then extend `CycleEntry` with optional fields:

- `prediction: LocalPrediction | None = None`
- `prediction_error: PredictionError | None = None`

This keeps backward compatibility by making the new fields optional.

### 2. Add a Prediction Protocol

Extend [interfaces.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/interfaces.py) with a new protocol, for example:

```python
class ExpectationModel(Protocol):
    def predict(
        self,
        state_before: Dict[str, float],
        available_actions: List[str],
        history: List[CycleEntry],
        substrate: MemorySubstrateProtocol | None = None,
    ) -> Dict[str, LocalPrediction]:
        ...

    def compare(
        self,
        prediction: LocalPrediction | None,
        state_after: Dict[str, float],
        dimensions: DimensionScores,
        coherence: float,
        delta: float,
    ) -> PredictionError | None:
        ...
```

This should be optional in the engine so old domains still run unchanged.

### 3. Add Optional Engine Hooks

Update [engine.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/engine.py) so the engine can:

- request action-conditioned predictions before selection
- pass predictions to the selector
- compute prediction error after execution
- store both in episodic memory

Minimal engine path:

1. observe current state
2. gather available actions
3. `predict()` for those actions if an expectation model exists
4. selector chooses using available actions, history, and predictions
5. execute chosen action
6. observe post-state
7. coherence model scores post-state
8. `compare()` prediction vs actual outcome
9. record cycle entry including prediction + prediction error

### 4. Extend Selector Contract Carefully

The current selector protocol is:

```python
select(available, history) -> (action, mode)
```

To preserve compatibility, avoid changing this immediately in a breaking way.

Suggested compatibility path:

- keep the current selector interface for now
- allow `RealCoreEngine` to inject prediction summaries into `state_before`
- or add a new optional selector subtype later:

```python
class PredictiveSelector(Protocol):
    def select(
        self,
        available: List[str],
        history: List[CycleEntry],
        predictions: Dict[str, LocalPrediction],
    ) -> Tuple[str, str]:
        ...
```

V1 recommendation:

- do **not** force a selector interface break yet
- let engine augment state and history first
- add a predictive selector in a second step

### 5. Add Prediction-Aware Consolidation

The consolidation pipeline in [consolidation.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/real_core/consolidation.py) should eventually promote not only:

- high-coherence attractors
- surprises from large delta
- boundary cases

but also:

- reliable predictors
- persistent false expectations
- situations where prediction error repeatedly points to the same missing distinction

V1 can defer full consolidation changes, but the design should anticipate them.

## Biological Framing

This proposal keeps REAL aligned with the repo's biological framing:

- memory is not just storage
- memory changes what the agent is ready to perceive
- memory changes what the agent expects
- learning happens partly by reducing costly surprise

That is closer to biological anticipatory regulation than the current mostly trial-and-error interpretation.

## What This Is Not

This proposal does **not** require:

- global backpropagation
- centralized policy optimization
- full generative world modeling
- explicit symbolic planning

It only requires local expectation and local prediction error.

## Phase 8 Mapping

If adopted in `real_core`, the current Phase 8 anticipation-like pieces become cleaner domain instances rather than special cases.

Examples:

- `source_sequence_transform_hint_*` becomes a domain-specific predicted action consequence
- latent-context confidence becomes a domain-specific recognition signal
- self-selected capability recruitment can respond to forecasted ambiguity, not only observed mismatch
- morphogenesis can be recruited by expected routing strain, not only accumulated strain

This would reduce the amount of anticipation logic currently smuggled into observation features in [environment.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/environment.py) and [selector.py](C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/phase8/selector.py).

## Recommended Implementation Path

### Phase 1: Structural Core Support

Goal:

- add prediction types
- add optional expectation interface
- store prediction + prediction error in cycle traces

No selector or domain behavior needs to change yet.

Acceptance:

- old domains still run unchanged
- engine can carry empty or optional predictions

### Phase 2: Phase 8 Predictive Binding

Goal:

- implement a Phase 8 expectation model that predicts:
  - expected transform fit
  - expected feedback quality
  - expected context stability
  - expected value of latent recruitment

Acceptance:

- predictions are local-only
- cycle entries show meaningful prediction error

### Phase 3: Predictive Selection

Goal:

- let selector weight expected outcome and uncertainty directly

Acceptance:

- on tasks like `B2`, the selector should follow strong source-sequence guidance more consistently once latent capability is active

### Phase 4: Predictive Consolidation

Goal:

- allow durable prediction structures to be promoted into substrate/carryover

Acceptance:

- repeated prediction-success patterns become cheaper and more stable
- repeated prediction-error patterns produce sharper contextual differentiation

## Immediate Practical Benefit

This proposal directly addresses the current Phase 8 tension:

- repeated experience helps `B2`
- idle runtime does not
- self-selected latent capability often forms before the selector fully uses it

That is exactly the situation where a predictive core should help.

## Recommendation

Treat this as a `real_core` architectural extension, not a Phase 8 workaround.

The missing element is not merely "more clever substrate features." The generalized REAL algorithm itself currently lacks a clean notion of:

- expected consequence
- uncertainty
- prediction error

Those should be promoted into the core abstraction.

## Proposed Next Concrete Step

Create a minimal implementation branch with only:

1. `LocalPrediction` and `PredictionError` types
2. optional `ExpectationModel` protocol
3. non-breaking engine support for recording predictions
4. one tiny Phase 8 expectation binding that predicts expected transform fit at the source node

That would be the smallest useful prototype of predictive REAL.
