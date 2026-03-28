# Layer 2 Regulatory Substrate Design

## Summary

The current fast layer is the main learner in REAL-NS. It accumulates local
credit and debt, maintains provisional versus durable support, tracks latent
context evidence, and adapts structure under pressure. The current slow layer,
by contrast, is mostly an adaptive controller over slice summaries. It is
useful, but it is not yet learning in the same qualitative way.

This note proposes a more aligned Layer 2: a small, slower REAL-like network
that regulates Layer 1 through compact summaries rather than raw runtime state.
It should preserve the role split:

- Layer 1 solves the task locally.
- Layer 2 regulates timing, hygiene, plasticity, settlement, and rescue.
- Layer 2 never selects task answers directly.

## Current Read

### What Layer 1 already has

Layer 1 already exhibits the main learning patterns we want to preserve:

- local credit and debt
- provisional versus durable support
- branch and context differentiation
- latent regime evidence accumulation
- decaying and consolidating memory
- structural adaptation through growth pressure and morphogenesis

Concretely, these patterns are visible in:

- `phase8/environment.py`
- `phase8/selector.py`
- `phase8/substrate.py`

### What Layer 2 currently lacks

The new `gradient` controller is better than the older threshold-heavy path,
but it still behaves more like a hand-shaped regulator than a distributed
learner. It mostly computes:

- `budget_target`
- `pressure_level`
- `hygiene_level`
- `growth_drive`
- `portfolio_drive`
- `settlement_confidence`

from summary features in one step, using smooth formulas in
`real_core/lamination.py`.

That means Layer 2 is currently missing several patterns that Layer 1 already
uses:

- distributed regulatory state
- provisional regulatory hypotheses
- persistent credit/debt per regulatory primitive
- competition among alternative regulatory responses
- slower latent-state tracking over slice sequences
- consolidation of successful regulatory motifs

## Design Principle

Layer 2 should not become a second task-solving network. It should become a
small abstract regulatory substrate whose units learn over compact slice
summaries.

The guiding rule is:

> Layer 1 learns task structure. Layer 2 learns regulatory structure.

That means Layer 2 should learn things like:

- when hygiene helps versus harms
- when unresolved debt calls for differentiation rather than more budget
- when growth-capable mode should open
- when ambiguity should be preserved longer
- when settlement is genuinely safe

## Layer 2 Pattern Mapping

Map the fast-layer patterns directly, but at a slower and more abstract level.

### 1. Local observation becomes summary-channel observation

Layer 1 observes packet-local state.
Layer 2 should observe slice-summary channels such as:

- floor accuracy gap
- aggregate accuracy gap
- context spread
- unresolved context debt mass
- ambiguity retention
- commitment hardness
- failed-hygiene persistence
- growth readiness and pressure
- slice efficiency
- settlement trend

These are already mostly available in `SliceSummary` and the current gradient
feature extraction path.

### 2. Local credit/debt becomes regulatory credit/debt

Layer 2 should maintain credit/debt per regulatory primitive, not just per
single combined policy.

Examples:

- hygiene primitive credit/debt
- differentiation primitive credit/debt
- growth primitive credit/debt
- settlement primitive credit/debt
- budget expansion primitive credit/debt
- ambiguity-preservation primitive credit/debt

The update target should be the observed effect on the specific problem that
primitive claims to regulate, not just aggregate accuracy.

Examples:

- differentiation gets credit when floor accuracy rises and spread falls
- hygiene gets debt when repeated drops do not reduce conflict or debt
- growth gets credit when structural expansion improves floor recovery
- settlement gets debt when it predicts readiness but the next slice degrades

### 3. Provisional versus durable support should exist in Layer 2

Layer 2 should not harden regulatory responses too quickly.

It should maintain:

- provisional support for candidate regulatory responses
- slower durable support for repeatedly validated responses

This is especially important for cases like:

- repeated rescue attempts
- uncertain growth initiation
- competing hygiene levels
- ambiguity-retention versus commitment

Without this, Layer 2 will keep behaving like a thresholded controller.

### 4. Competition should happen among regulatory primitives

Layer 2 should not choose one giant monolithic policy label.

Instead, a small number of regulatory nodes should compete and cooperate over
continuous outputs. The output signal should be composed from several partial
pressures, for example:

- `budget_drive`
- `hygiene_drive`
- `differentiation_drive`
- `growth_drive`
- `settlement_drive`
- `portfolio_drive`

Those drives then map into the existing `RegulatorySignal`.

### 5. Layer 2 needs its own latent-state tracking

Layer 1 has latent context trackers for hidden task structure.
Layer 2 should have an analogous slower mechanism for hidden regulatory state.

Examples of latent regulatory state:

- "weak branch is unstable but recoverable"
- "run is poisoned and needs real hygiene"
- "growth is structurally needed"
- "ambiguity is still productive"
- "system is confidently wrong"

This should not be a giant symbolic planner. It should be a small slow-memory
tracker over slice-sequence evidence.

### 6. Consolidation should exist at Layer 2

Layer 2 should retain regulatory motifs that repeatedly help and allow weak or
contradictory motifs to decay.

That means:

- keep a compact episodic record of recent regulatory episodes
- consolidate recurring successful motifs into durable slow support
- keep surprise and boundary episodes for later rescue use

This is already conceptually compatible with the core carryover and
consolidation machinery in `real_core`.

## Proposed Layer 2 Structure

## Regulatory primitives

Start with a small fixed set of regulatory primitives:

- `differentiate`
- `hygiene`
- `stabilize`
- `expand`
- `settle`
- `explore`

These are not direct actions. They are slow-layer control themes.

### Differentiate

Purpose:

- recover weak branches
- reduce context spread
- increase floor accuracy

Outputs:

- more weak-branch pressure
- less premature commitment
- stronger rescue bias

### Hygiene

Purpose:

- challenge stale or poisoned structure
- reduce harmful carryover

Outputs:

- hygiene intensity
- reset depth
- consolidation suppression

### Stabilize

Purpose:

- preserve useful progress
- reduce oscillation and overreaction

Outputs:

- lower hygiene
- lower exploratory pressure
- preserve provisional gains

### Expand

Purpose:

- increase structural/plastic capacity when Layer 1 is persistently stuck

Outputs:

- growth-capable drive
- persistence of growth window
- slight budget increase

### Settle

Purpose:

- determine whether closure is safe

Outputs:

- settlement confidence
- stop pressure

### Explore

Purpose:

- preserve alternative rescue hypotheses
- trigger rescue portfolio behavior

Outputs:

- portfolio drive
- ambiguity-preservation pressure
- duration variation

## Proposed state per Layer 2 primitive

Each slow primitive should maintain a compact local state analogous to Layer 1
node state:

- `activation`
- `provisional_support`
- `durable_support`
- `credit`
- `debt`
- `velocity`
- `age`
- `last_effect`

This can be implemented first without introducing a full graph of regulatory
nodes. A small typed state table would already be a large step forward.

## Proposed Layer 2 interactions

Use a small substrate or mesh among primitives.

Example couplings:

- `differentiate` supports `explore` when spread is high
- `hygiene` suppresses `settle` while debt is high
- `stabilize` suppresses `expand` when floor and aggregate are already healthy
- `expand` supports `differentiate` when repeated rescue fails
- `settle` supports `stabilize` when floor and aggregate remain healthy

This is closer to the biological framing than one monolithic controller score.

## How Layer 2 would learn

Each slice becomes one regulatory episode.

At time `t`, Layer 2:

1. observes compact slice-summary channels
2. activates primitive supports
3. composes a continuous `RegulatorySignal`
4. Layer 1 runs
5. Layer 2 sees the next slice summary
6. Layer 2 updates primitive credit/debt based on what improved or worsened

The key is that regulatory credit assignment should be local to the primitive.

Examples:

- if floor rises and spread falls after strong differentiation pressure,
  `differentiate` earns credit
- if hygiene is high but conflict and debt stay high, `hygiene` earns debt
- if growth initiation opens and floor begins recovering, `expand` earns credit
- if portfolio rescue runs but winner selection still leaves one branch dead,
  `explore` or `differentiate` may earn debt depending on the failure pattern

## How this should connect to current code

### Reuse

Keep these existing pieces:

- `SliceSummary`
- `RegulatorySignal`
- `SliceExecutionPlan`
- bounded adaptive slice execution
- rescue portfolio and winner-takes-state semantics

### Replace or evolve

The part to evolve is the single-step gradient controller in
`real_core/lamination.py`.

Instead of one formula pass, introduce a `RegulatorySubstrate` that:

- stores primitive-level slow state
- updates primitive credit/debt after each slice
- composes the continuous control vector

The current gradient features can become the first observation channels for
that substrate.

### Transitional architecture

#### Phase 1

Implement a compact primitive-state table:

- no full node graph yet
- no symbolic planner
- one state record per primitive

#### Phase 2

Add primitive interactions through a small mesh or coupling matrix.

#### Phase 3

Move rescue portfolio trigger, growth initiation, and settlement confidence out
of hand-shaped formulas and into primitive competition/composition.

## Minimal implementation sketch

Add new core types:

- `RegulatoryPrimitive`
- `RegulatoryPrimitiveState`
- `RegulatoryObservation`
- `RegulatoryComposition`
- `RegulatorySubstrate`

Proposed primitive enum:

- `DIFFERENTIATE`
- `HYGIENE`
- `STABILIZE`
- `EXPAND`
- `SETTLE`
- `EXPLORE`

Proposed update loop:

1. `RegulatoryObservation.from_slice_history(history)`
2. `RegulatorySubstrate.observe(...)`
3. `RegulatorySubstrate.compose_signal(...)`
4. fast layer runs
5. `RegulatorySubstrate.apply_feedback(previous_signal, next_summary)`

## Why this is aligned

This direction is aligned with the project’s biology-inspired framing because
it avoids two failures:

- a brittle top-down planner
- an underpowered single slow-node controller

Instead it gives Layer 2 the same family of mechanisms Layer 1 already uses,
but at a slower, coarser, and more abstract level.

That is probably the cleanest way to let Layer 2 actually learn in its own way
without violating the architecture’s localist and regulatory principles.

## Recommended next step

Do not jump straight to a full Layer 2 graph.

The best v0 is:

1. add primitive-level slow state in `real_core`
2. move the current gradient features into primitive observations
3. update primitive credit/debt slice by slice
4. compose `RegulatorySignal` from primitive activations
5. keep current compatibility outputs in Phase 8

That would let us test whether a genuinely slow-learning regulatory substrate
outperforms the current formula-heavy gradient controller before adding more
complexity.
