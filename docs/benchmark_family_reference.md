# Benchmark Family Reference

This document is a plain-language reference for the task families used in the
REAL Phase 8 and laminated benchmark runs.

It is meant to answer:

- what the benchmark families are
- what `task_a`, `task_b`, and `task_c` mean
- what the benchmark IDs like `B2S3` or `C3S1` mean
- what each family is actually testing
- why some families are harder than others

## Core Idea

Most of these benchmarks use the same basic symbolic substrate:

- 4-bit input patterns
- a small set of discrete transforms
- a routing topology with a `source` and `sink`
- repeated online packet delivery rather than offline batch training

The transforms used across the repo are:

- `rotate_left_1`
- `xor_mask_1010`
- `xor_mask_0101`
- `identity`

The benchmark families differ in **what determines the correct transform**:

- sometimes visible context directly determines it
- sometimes a hidden memory state determines it
- sometimes the visible cue is only a weak or misleading proxy
- sometimes the system must infer an entirely hidden regime from sequence history

## Common Task Meanings

For the visible-context A/B/C-style families, the task keys usually mean:

| Task | Context 0 | Context 1 |
| --- | --- | --- |
| `task_a` | `rotate_left_1` | `xor_mask_1010` |
| `task_b` | `rotate_left_1` | `xor_mask_0101` |
| `task_c` | `xor_mask_1010` | `xor_mask_0101` |

So:

- `task_a` is the most "default" split
- `task_b` changes only the odd / second branch
- `task_c` removes `rotate_left_1` from the even branch and makes both branches XOR-family transforms

That matters because `task_b` and `task_c` are often where stale carryover or
overgeneralized transform learning shows up first.

## Visible vs Latent vs Hidden

There are three related ideas that show up across the repo:

- `visible`
  - the context label is explicitly present on the packet
- `latent`
  - the true context exists in the task definition, but the label is not exposed
- `hidden`
  - used mainly in the HR family; the correct transform depends on a hidden regime inferred from sequence history

In practice:

- visible-mode tasks test whether the system can use explicit relational cues
- latent/hidden-mode tasks test whether it can infer the right controller from history and local evidence

## Family A: Scale / Horizon

**What it tests**

Family A is the cleanest family. Visible context fully determines the correct
transform. There is no real ambiguity about what should happen. The main
difficulty is scale:

- more nodes
- more packets
- deeper topologies
- longer online runs

So Family A mostly tests:

- routing headroom
- topology scale
- whether the system can preserve correct visible-context mappings as workload grows

**How the IDs work**

- `A1` = smallest stage-1 anchor
- `A2` = larger topology
- `A3` = scale topology
- `A4` = ceiling topology
- `A5-A6` = aspirational larger generated scales

**Representative scales**

From the suite definitions and scenario docs:

- `A1`: about 6 nodes / 18 examples
- `A2`: about 10 nodes / 36 examples
- `A3`: about 30 nodes / 108 examples
- `A4`: about 50 nodes / 216 examples

**Interpretation**

If the system struggles on A, that usually means something broad is wrong:

- routing instability
- context usage failure
- bad carryover
- general control problems

Because A does not require deep hidden-state inference, it is usually the most
forgiving family.

## Family B: Hidden Memory

**What it tests**

Family B introduces a hidden memory controller. A visible context bit may still
exist, but it is not the real source of truth. The correct transform depends on
an underlying memory state derived from prior sequence history.

So Family B mainly tests:

- sequential hidden-state tracking
- whether the system can avoid over-trusting visible context
- whether it can keep multiple context-conditioned hypotheses alive long enough

**How the IDs work**

The B-family IDs have two parts:

- the leading number is the hidden memory window
- the `S` number is the scale point

Examples:

- `B2S1`
- `B2S2`
- `B2S3`

In the current laminated work, `B2...` is the main active branch:

- `B2` means the hidden controller depends on a 2-step memory window
- `S1/S2/S3/...` scale topology and run length upward

**Representative scales**

The suite defines:

- `B2S1`: 6-node / 18-example hidden-memory anchor
- `B2S2`: 10-node / 36-example large-topology point
- `B2S3`: 30-node / 108-example scale point
- `B2S4`: 50-node / 216-example ceiling point

with larger aspirational extensions after that.

**Interpretation**

Family B is where the system first has to do more than just route and apply a
visible rule. It has to infer or preserve hidden state online.

This is why B often reveals:

- one-context collapse
- premature transform commitment
- carryover poisoning
- mismatch between slow-layer rescue and fast-layer local differentiation

## Family C: Transform Ambiguity

**What it tests**

Family C is the ambiguity family.

The visible cue becomes progressively less informative about the correct
transform. In the harder C points, both visible branches can be ambiguous, and
the true transform depends on a richer hidden controller rather than a clean
visible label.

From the earlier family report:

- `C1` is clean: visible context still determines the transform
- `C2` introduces partial ambiguity
- `C3/C4` make both visible branches ambiguous
- the underlying controller is effectively a 4-state ambiguity process

In the current laminated `C3S...` scale suite, the family is built around this
same style of ambiguity challenge and then scaled across topology sizes.

So Family C mainly tests:

- latent-state inference under weak observation
- holding ambiguity without collapsing too early
- learning differentiated structure instead of a single dominant scaffold
- whether growth or rescue actually builds useful alternative structure

**How the IDs work**

The current laminated C scale IDs are:

- `C3S1`
- `C3S2`
- `C3S3`
- `C3S4`

The `C3` prefix reflects the C3-style ambiguity pattern as the base challenge,
and the `S` number scales topology and run length.

**Representative scales**

The suite defines:

- `C3S1`: 6-node / 18-example ambiguity anchor
- `C3S2`: 10-node / 36-example ambiguity point
- `C3S3`: 30-node / 108-example ambiguity point
- `C3S4`: 50-node / 216-example ambiguity point

with larger generated extensions after that.

**Interpretation**

C is currently one of the hardest families because it combines:

- weak observability
- multistate hidden control
- online adaptation
- transform-family competition

This is also why ordinary neural baselines struggled badly on the earlier
`C1-C4` ceiling family: once the visible cue stopped cleanly identifying the
transform, the task became a real latent-inference problem rather than a simple
mapping problem.

## Hidden-Regime Family (HR)

**What it tests**

The HR family is a more explicit hidden-controller benchmark.

Instead of "visible context is ambiguous," the task is framed directly as:

- there is an unobserved regime
- the regime is derived from recent sequence parity
- the correct transform depends on that regime

So HR mainly tests:

- forecasting hidden controller state
- sequence-memory integration
- regime inference without explicit labels
- slow-layer regulation under hidden uncertainty

**How the IDs work**

The built-in hidden-regime cases are:

- `HR1`
- `HR2`
- `HR3`
- `HR4`

From `phase8/hidden_regime.py`:

- `HR1`
  - binary hidden regime
  - driven by parity of the previous symbol
  - compact 4-node topology
  - sequence memory window `1`
- `HR2`
  - binary hidden regime
  - driven by a 3-step parity window
  - sequence memory window `3`
- `HR3`
  - four hidden regimes derived from the last two parity observations
  - sequence memory window `2`
- `HR4`
  - binary hidden regime with a mid-run remapping of regime-to-transform bindings
  - forces post-shift adaptation

**HR task meanings**

For binary HR cases, the task maps are the same two-context maps used in A/B/C:

| Task | Regime 0 | Regime 1 |
| --- | --- | --- |
| `task_a` | `rotate_left_1` | `xor_mask_1010` |
| `task_b` | `rotate_left_1` | `xor_mask_0101` |
| `task_c` | `xor_mask_1010` | `xor_mask_0101` |

For the 4-regime case (`HR3`), each task uses all four transforms:

| Task | Regime 0 | Regime 1 | Regime 2 | Regime 3 |
| --- | --- | --- | --- | --- |
| `task_a` | `rotate_left_1` | `xor_mask_1010` | `xor_mask_0101` | `identity` |
| `task_b` | `rotate_left_1` | `xor_mask_0101` | `identity` | `xor_mask_1010` |
| `task_c` | `xor_mask_1010` | `xor_mask_0101` | `rotate_left_1` | `identity` |

That makes `HR3` especially useful for testing whether the system can maintain a
more structured latent regime representation instead of collapsing everything to
one dominant transform family.

## How the Families Relate

One good way to think about the progression is:

1. **A family**
   - "Can you route and apply the right visible rule as scale grows?"
2. **B family**
   - "Can you infer hidden memory state instead of over-trusting visible context?"
3. **C family**
   - "Can you preserve ambiguity and differentiate correctly when visible cues are weak or misleading?"
4. **HR family**
   - "Can you explicitly infer hidden regimes from sequence history and regulate yourself under hidden uncertainty?"

So in a rough sense:

- A is about scale
- B is about hidden memory
- C is about ambiguity
- HR is about hidden-regime forecasting

## Why `task_b` and `task_c` Often Fail First

Across several families, `task_b` and especially `task_c` are more fragile than
`task_a` because they are more likely to expose:

- stale context bindings
- overgeneralization of one transform family
- weak-branch collapse
- wrong reuse of earlier substrate support

`task_a` often benefits from being the most "natural" or baseline split in the
transform map. `task_b` and `task_c` are where the system has to prove it is
really learning the mapping, not just reusing a dominant scaffold.

## How to Read Benchmark IDs Quickly

Short cheat sheet:

- `A1-A4`
  - clean visible-context family, scaling up
- `B2S1-B2S...`
  - hidden-memory family with 2-step memory window, scaling up
- `C3S1-C3S...`
  - ambiguity-heavy family, scaling up
- `HR1-HR4`
  - hidden-regime forecasting family

The trailing `S` number usually means:

- larger topology
- more packets/examples
- deeper or broader run

## Practical Benchmark Reading Tips

When reading experiment outputs:

- look at `final_accuracy`
  - overall aggregate accuracy
- look at `floor_accuracy`
  - worst-context or worst-regime performance
- if aggregate is decent but floor is poor
  - that usually means one branch or regime is carrying the run while another is failing
- in A/B/C visible tasks, the context breakdown is often the most revealing part
- in HR tasks, regime inference and forecast metrics matter more than simple visible context splits

## Current Big-Picture Use

In recent laminated development, these families have been useful for different
roles:

- **A**
  - backwards compatibility and sanity checks
- **B**
  - debugging one-context collapse and premature commitment
- **C**
  - debugging ambiguity retention, structural rescue, and growth usefulness
- **HR**
  - checking hidden-regime regulation and whether improvements transfer beyond visible-context tasks

That is why a change can look "good" on A and B but still fail on C, or help HR
without fixing the visible ambiguity problem.
