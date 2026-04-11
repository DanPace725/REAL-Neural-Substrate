# 2026-03-31 0135 - REAL Stock Take After C Task Retuning

## Why

After a long C-family tuning pass, the codebase ended up with a mix of:

- real correctness fixes
- useful diagnostic instrumentation
- C-specific scaffolds that can drive performance up in narrow windows
- regulator logic that looked promising until a metadata bug was fixed

This trace separates those categories so we do not confuse:

- "the architecture genuinely improved"
with
- "the benchmark can be pushed upward under a fragile assisted regime"

## What Looks Safe To Keep

### 1. Two-slice threshold settlement guard

The heuristic / learning settle path now requires at least two slices before an
explicit accuracy threshold can settle a run.

Why keep it:

- it fixed the false one-slice settle loophole
- it applies to all families, not just C
- it makes threshold-based evaluation more honest

Relevant file:

- `real_core/lamination.py`

### 2. Metadata overwrite fix in slice summaries

The slice summary path in Phase 8 previously let stale applied-signal metadata
overwrite the freshly computed `c_task_regime_summary`.

Why keep it:

- this was a real correctness bug
- it affected interpretation of runs
- it was making Layer 2 reason from stale regime data

Relevant file:

- `phase8/lamination.py`

### 3. Explicit-state instrumentation

The C-task packet / node state now exposes an explicit transform-belief register:

- packet belief distribution
- packet top hypothesis
- packet hypothesis confidence
- node-local mirrored hypothesis state

Why keep it:

- it gives interpretable readout into what the substrate thinks is happening
- it aligns with the earlier redesign intuition about local adaptive code
- it is useful even when it is not yet good enough to drive policy

Important caveat:

- this looks safe as instrumentation / observation
- it is not yet validated as a strong control signal

Relevant files:

- `phase8/models.py`
- `phase8/environment.py`
- `phase8/selector.py`
- `phase8/lamination.py`

## What Should Stay Quarantined As Experimental

### 1. `stabilized` C-task Layer 1 mode

This mode answered an important question:

- yes, the system can do much better when Layer 1 follows "resolve once, preserve after"

But it is still heavy assist. It is closer to guided execution than an endogenous
REAL mechanism.

Keep as:

- benchmark probe
- upper-bound scaffold
- debugging aid

Do not treat as:

- a general REAL update

### 2. `communicative` C-task Layer 1 mode

This is the most interesting scaffold because it recovers a large part of the
stabilized gain with softer packet-level preserve / reopen signaling.

Why it is still experimental:

- it is still task-scoped to C
- it still depends on carefully tuned thresholds
- it enters narrow good pockets rather than broad robust competence

Keep as:

- a developmental probe of the right mechanism
- evidence that inter-node epistemic communication matters

Do not yet treat as:

- mainline REAL behavior

### 3. C-task Layer 2 regulatory profile

Once the stale-metadata bug was fixed, the apparent improvement from Layer 2's
new C-task profile mostly disappeared.

Corrected baseline comparisons:

- `C3S2 / task_a / visible / learning` -> `0.711`
- `C3S2 / task_a / visible / heuristic` -> `0.775`
- `C3S2 / task_c / visible / learning` -> `0.675`
- `C3S2 / task_c / visible / heuristic` -> `0.750`

Interpretation:

- Layer 2 is not yet the winning lever on corrected C runs
- the `learning` regulator is currently weaker than `heuristic`
- the new explicit-state observation path is not the problem by itself
- the C-task Layer 2 policy logic is still not ready for promotion

## What The C Pass Actually Taught Us

### 1. The old `.5-.6` ceiling was not a hard capacity ceiling

The system can reach `>.8` on some visible C runs, consistently, under narrow
parameter windows.

That means:

- REAL is not fundamentally incapable of C-like behavior
- the substrate can enter a competent regime
- but that regime is narrow and fragile

This points more to:

- phase selection
- metastability
- insufficient regulation of an already-possible computation

than to total absence of capability.

### 2. Layer 1 is still the main bottleneck

The strongest finding from forcing and teacher-trace work was:

- source errors matter
- but fixing only the source is not enough
- when early hops are corrected, divergence moves deeper into the graph
- only broad path correction rescues the hard cases

Interpretation:

- failure is distributed through Layer 1
- the substrate still lacks reliable preservation of a correct intermediate state

### 3. Inter-node communication matters

The communicative scaffold was the most informative intervention.

What it suggests:

- nodes need more than payload and delayed reward
- they need a shared way to communicate something like:
  - unresolved
  - provisionally resolved
  - preserve by default
  - reopen if contradiction rises

This is probably the most durable architectural lesson from the whole pass.

### 4. C asymmetry is still the same old asymmetry

The weak branch remained `context_0`.

`task_a` and `task_c` diverged not because one was broken from slice 1, but
because:

- both start similarly
- both later enter a preserve-heavy regime
- `task_c` is worse at maintaining weak-context differentiation once in that regime

That makes the current problem look less like "task_c is special" and more like:

- weak-context rescue is still fragile
- xor-vs-xor style distinctions are harder to preserve than rotate-vs-xor

## What Generalization Looks Like Right Now

The truly general changes appear safe.

Cross-family smoke checks on the standard laminated path:

- `A2 / task_a / visible / heuristic` -> `1.000`, settled in 2 slices
- `A2 / task_a / visible / learning` -> `1.000`, settled in 2 slices
- `B2S1 / task_b / visible / heuristic` -> `1.000`, settled in 2 slices
- `B2S1 / task_b / visible / learning` -> `1.000`, settled in 2 slices

Important note:

- the A/B runner intentionally rejects C-only topology overrides
- so these smoke checks are the right check for genuinely global changes

Interpretation:

- the broad REAL fixes above do not appear to harm representative A/B runs
- the C-task scaffolds are still scoped to C and should remain scoped for now

## Current Architectural Position

The present best interpretation is:

- keep the real correctness fixes
- keep the explicit-state machinery as instrumentation
- keep the C communicative / stabilized paths as experimental probes
- do not yet merge the C-specific Layer 2 policy logic into the main story of REAL

The main open architectural question is no longer:

- "can REAL ever solve C?"

It is closer to:

- "how does REAL learn to recognize and preserve the narrow regime in which it already can?"

## Recommended Next Step

Before more tuning, do a synthesis pass that answers three questions cleanly:

1. Which mechanisms are genuinely architectural?
2. Which ones are benchmark scaffolds that taught us something but should stay quarantined?
3. What is the smallest endogenous mechanism that could replace the communicative scaffold?

My current answer to #3 is still:

- some form of inter-node epistemic communication
- probably tied to a compact local adaptive code
- probably expressing resolve / preserve / reopen state
- and probably needing better Layer 2 phase regulation later, not first

## Bottom Line

The week of C-task work did not produce a clean generalized fix. But it did
produce something valuable:

- a corrected, honest baseline
- a clearer separation between global REAL improvements and task-specific assists
- and a much stronger clue about the missing endogenous mechanism

The biggest durable lesson is that REAL seems less blocked by lack of raw
expressive power than by lack of robust communication and preservation of
resolved state inside Layer 1.
