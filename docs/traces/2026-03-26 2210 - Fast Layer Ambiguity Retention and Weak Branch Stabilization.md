# 2026-03-26 2210 - Fast Layer Ambiguity Retention and Weak Branch Stabilization

## Purpose

Record the work completed after
`docs/traces/2026-03-26 1645 - Laminated Context Collapse and Differentiation Reframe.md`,
with emphasis on:

- the fast-layer investigation that followed the slow-layer differentiation work
- the move from context-drop bugs to premature transform-family commitment
- the new provisional-support / ambiguity-retention machinery
- the targeted weak-branch commitment damp
- the current benchmark picture on B, hidden-regime, and C-family quick runs

## Summary

The main conclusion from this phase is:

- the slow layer was not the primary remaining blocker on the hard B cases
- the fast layer was still losing or overcommitting context-specific structure
- the first successful fixes came from repairing local observability and local
  transform competition, not from making the slow layer more directive

The path of the investigation went roughly like this:

1. the slow layer was given better asymmetry awareness and persistent
   context-debt tracking
2. that made it clear the slow layer could see the failed branch but still
   could not rescue it through bias alone
3. inspection then showed downstream nodes often had packet context physically
   present but locally unavailable, and in some cases could not even try
   non-identity transforms
4. after fixing those fast-layer issues, the failure shifted from
   `identity` fallback to premature commitment to the wrong non-identity
   transform family
5. a global ambiguity-retention update helped, but was not stable enough on its
   own
6. a targeted weak-branch commitment damp produced the strongest improvement:
   `B2S3 task_c` moved from chronic collapse into successful short-horizon
   settlement in isolated runs

So the architecture is now closer to the intended biological/TCL picture:

- slow layer detects unresolved branch debt and biases recovery
- fast layer retains local ambiguity/provisional support longer where needed
- the weak branch can stay plastic without forcing the whole network into
  prolonged indecision

## Phase 1 Alignment

This phase moved the implementation closer to the Phase 1 framing in three
important ways.

From Relational Primitives:

- local substrate state should preserve unresolved relation structure rather
  than flattening it into aggregate success
- ambiguity should be a live dynamical condition, not just a post hoc metric
- failed differentiation should remain locally meaningful long enough for
  correspondence to be restored

From TCL:

- the slow layer should tilt or bias the fast layer rather than directly solve
  the task
- slow control should not continuously reach down into local action selection
- stability should come from local recovery under regulatory pressure, not from
  top-down override

From AVIA:

- higher-order state should summarize and modulate lower-order processing
  without erasing lower-order organization
- higher-order intervention is most appropriate when local structure is failing
  to differentiate, not when local processing simply needs more brute force

The changes below were guided by that interpretation.

## What Changed

### 1. Slow-layer context debt was added

The slow layer now carries a persistent per-context debt/credit style signal,
analogous to the fast-layer credit/debt machinery.

That added:

- `max_context_debt`
- `total_context_debt`
- `open_context_count`
- `best_debt_context`

Effect:

- the slow layer no longer forgets which context is still unresolved
- rescue pressure can stay focused on the weak branch across slices
- settlement cannot be confused by aggregate improvement alone

This did not solve the hard cases by itself, but it clarified that the
remaining issue was downstream in the fast layer.

### 2. Packet context was preserved as a usable local signal

We found that downstream nodes often still had packet context physically present
while their local observation path exposed no usable context.

That was fixed by separating:

- packet-carried context
- visible/effective context
- context confidence

Added observation signals included:

- `packet_has_context`
- `packet_context_bit`
- `packet_context_confidence`
- `visible_context_exposed`

Effect:

- downstream nodes no longer become fully blind just because explicit visible
  context is suppressed
- local routing and transform competition can still condition on a low-confidence
  relational cue

### 3. The latent downstream transform gate was softened

We found a hard fast-layer action gate that removed all non-identity
`route_transform:*` actions downstream when explicit context was hidden and
latent promotion was not yet ready.

That was changed so that when packet context and task cues are still present,
the backend can keep a narrow non-identity transform set available.

Effect:

- the system stopped getting forced into pure `identity` fallback at the point
  of hidden downstream uncertainty
- transform-family failures became visible as true competition failures rather
  than impossible-action artifacts

### 4. Context-indexed feedback credit now falls back to packet context

Another fast-layer issue was that context-specific feedback ledgers were still
being keyed only from `effective_context_bit`.

That meant:

- packet context could still exist
- but context-specific credit/debt would remain near zero
- generic transform credit would dominate early and globalize too fast

This was changed so hidden packet context can still expose
`context_feedback_credit_*` and related context-specific ledger terms.

Effect:

- local transform competition became genuinely context-conditioned in more of
  the hidden or partially hidden path
- `B2S2 task_c` improved dramatically once this was in place

### 5. Added provisional transform support and ambiguity-retaining competition

To avoid hard-coding another gate, the fast layer was extended with a
provisional-versus-durable support split.

New state:

- `provisional_transform_credit`
- `provisional_context_transform_credit`

New local observation terms:

- `provisional_feedback_credit_*`
- `provisional_context_feedback_credit_*`
- `provisional_context_ambiguity`
- `transform_commitment_margin`

New behavior:

- new or weakly differentiated support first accumulates in provisional form
- generic durable promotion is damped when cross-context contradiction is still
  present
- selector exploration and route sampling flatten when ambiguity is high and
  commitment margin is low

Effect:

- the system can retain provisional competition longer without another brittle
  hard gate
- on hard cases this shifted the failure from immediate collapse into a more
  informative regime where ambiguity existed but did not always stabilize

### 6. Surfaced ambiguity and commitment aggregates into slice summaries

The fast-layer ambiguity signals were then aggregated into slice metadata so
they could be inspected at the laminated level.

Added slice metadata includes:

- `mean_provisional_context_ambiguity`
- `max_provisional_context_ambiguity`
- `mean_transform_commitment_margin`
- `min_transform_commitment_margin`
- hidden-packet variants of the same metrics

Effect:

- we could tell whether the hard cases were failing because ambiguity never
  appeared, or because ambiguity appeared and then collapsed too quickly
- this showed that the problem had shifted to re-sharpening / premature
  recommitment, especially on `B2S3 task_c`

### 7. Tried a global slowdown, then tuned it back

We tried slowing generic promotion and extending provisional persistence more
globally.

That confirmed a real part of the diagnosis:

- ambiguity stayed alive longer
- but the network could drift into broader unstable competition or slower
  convergence

So the pure global slowdown was backed off. It was useful diagnostically, but
not the best end-state.

### 8. Added targeted weak-branch commitment damp

The most effective recent change was targeted rather than global.

The laminated runner already knew:

- `weak_context_bit`
- `weak_context_gap`

Those are now stored as fast-layer bias state and used only on the unresolved
branch.

New fast-layer weak-branch state:

- `slow_weak_context_bit`
- `slow_weak_context_gap`
- local observation markers such as `slow_weak_context_match`

Behavior:

- when feedback belongs to the unresolved branch, durable generic promotion is
  damped
- provisional support is boosted slightly on that branch
- the weak branch stays plastic longer without slowing the whole substrate down

This is much closer to the intended slow-layer role:

- Layer 2 does not prescribe the answer
- it only biases the fast layer to avoid overcommitting on the unresolved branch

## Validation

Focused validation now covers:

- packet-context fallback visibility
- hidden downstream transform availability
- provisional ambiguity observation
- provisional-vs-generic feedback update behavior
- slice metadata surfacing of ambiguity/commitment signals
- weak-context bias propagation from laminated regulation into the environment

Focused command at the end of this trace:

```text
python -m unittest tests.test_phase8_lamination tests.test_latent_route_transform_gate tests.test_lamination
```

Result:

- `32` tests passing

## Benchmark Results

### B family quick sweep

Quick sweep settings:

- visible mode
- `real` regulator
- seed `13`
- initial budget `6`
- threshold `0.8`
- safety `20`

Quick sweep outcome:

- `B2S1 task_a`: continue, `final=0.8214`, `floor=0.5`
- `B2S1 task_b`: settle in `8` slices, `final=0.8125`, `floor=0.8`
- `B2S1 task_c`: settle in `3` slices, `final=0.9167`, `floor=0.8333`
- `B2S2 task_a`: settle in `12` slices, `final=0.9375`, `floor=0.8333`
- `B2S2 task_b`: settle in `20` slices, `final=0.8611`, `floor=0.8462`
- `B2S2 task_c`: settle in `8` slices, `final=0.9286`, `floor=0.875`
- `B2S3 task_a`: continue, `final=0.8889`, `floor=0.8846`
- `B2S3 task_b`: continue, `final=0.8`, `floor=0.6667`
- `B2S3 task_c`: quick sweep instance was unstable, but isolated reruns became strong

Representative isolated rerun after the weak-branch damp:

- `B2S3 task_c`: settle in `11` slices with
  `final_accuracy = 0.9583`, `floor_accuracy = 0.9444`

Interpretation:

- `B2S2` is now in much better shape
- `B2S1` is mostly healthy except for `task_a`
- `B2S3` is improved but still less stable than the smaller scales

### Hidden-regime quick runs

Quick HR settings:

- hidden observable
- `real` regulator
- seed `13`
- initial budget `6`
- threshold `0.8`
- safety `20` and then `30`

At safety `20`:

- only `HR2 task_c` settled (`0.875`)
- most others remained below threshold

At safety `30`:

- no task settled
- several runs were worse than the shorter pass

Interpretation:

- the recent fast-layer fixes that helped visible B tasks do not yet transfer
  cleanly to HR
- HR appears to be a different failure mode, likely more tied to hidden-regime
  forecasting or capability/regime dynamics than to the specific visible-context
  branch-collapse issue

### C-family quick runs

Quick C settings:

- visible mode
- `real` regulator
- seed `13`
- initial budget `6`
- threshold `0.8`
- safety `20`

For `C3S1` to `C3S3`, none of the quick runs settled.

Nearest threshold:

- `C3S2 task_a`: `0.75`
- `C3S3 task_c`: `0.7667`

We then ran `C3S1` to safety `50`:

- `task_a`: continue, `0.3333`
- `task_b`: continue, `0.696`
- `task_c`: continue, `0.5859`

Interpretation:

- `C3S1` does not look simply slice-limited
- longer runs did not produce stable convergence
- C still looks like an ambiguity/path-dependence family rather than a
  straightforward horizon-limited one

## What the Metrics Showed

The new ambiguity and commitment metrics clarified the hard B case.

For `B2S3 task_c`, before the targeted weak-branch damp:

- ambiguity did appear early
- then hidden-packet ambiguity often collapsed too quickly
- commitment margins rose while the weak branch was still wrong
- debt stayed high even after ambiguity had mostly disappeared

That indicated:

- the fast layer was becoming confidently wrong on the unresolved branch
- pure global slowing was too blunt

After the weak-branch damp:

- the unresolved branch could stay plastic without making the whole network
  indecisive
- strong isolated `B2S3 task_c` recoveries became possible

So the key improvement was not "more ambiguity everywhere." It was:

- preserve ambiguity specifically where the slow layer has evidence that one
  branch is still owed recovery

## Current Read

The current architecture is in a better place than it was at the previous trace.

What now looks solid:

- fast-layer context visibility is healthier
- hard downstream gating bugs are removed
- provisional support and ambiguity are real substrate dynamics now
- the weak-branch targeted damp is the best-performing recent fix
- B-family visible tasks are materially healthier than before

What still looks open:

- `B2S3` stability is improved but not yet fully robust
- HR is still noisy and likely represents a different problem family
- C remains weak and does not appear to be merely slice-starved

## Recommended Next Steps

1. Treat the weak-branch targeted damp as the current best direction for B-family
   visible work, and test it more for stability rather than replacing it
   immediately.

2. Separate the next investigations by family:

   - B: robustness / variance / seed sensitivity
   - HR: hidden-regime-specific dynamics
   - C: ambiguity/path-dependence and carryover interaction

3. For the next detailed diagnostic, inspect a C-family failure
   (`C3S1 task_c` is the clearest current candidate), since B has now crossed
   into a more stable state while C remains clearly unresolved.
