# 2026-03-19 1151 - Session Synthesis Anticipation Self Selection and Carryover

**Type:** Session synthesis  
**Covers:** The anticipation / recognition / self-selection / transfer-carryover thread across the 2026-03-18 evening and 2026-03-19 follow-up traces  
**Primary seeds referenced:** 13, 23, 37, 51  

---

## Executive Summary

This session started from one architectural question:

> can REAL learn when to recruit its own capabilities rather than having latent/growth modes selected externally?

The answer at the end of the session is:

- **partially yes at the infrastructure level**
- **not yet decisively yes at the benchmark-behavior level**

The biggest achievements were not a single benchmark jump from self-selection alone. The strongest session-level progress was:

1. **REAL now has a genuine anticipation path in `real_core`.** Recognition and prediction are no longer implicit heuristics only; they are now first-class engine concepts.
2. **Phase 8 now actually uses that anticipation path.** Recognition and prediction both fire in real task runs and can influence selection locally.
3. **Transfer/carryover got materially better once stale carried supports were treated more like priors than commands.** This produced the largest practical gains of the session.
4. **Self-selected REAL is now operating with earlier and richer local evidence than before, but the hardest cases still expose a selector-use gap rather than a pure sensing gap.**

The clearest unresolved issue is now `C3`: prediction exists early, latent activation happens, but the visible self-selected path still collapses into a stable `rotate_left_1` attractor before latent use becomes behaviorally decisive.

---

## Thread 1: Self-Selected Capability Recruitment

The session began by replacing external mode choice with a substrate-internal capability-control layer. The implemented direction was:

- keep legacy fixed policies:
  - `fixed-visible`
  - `fixed-latent`
  - `growth-visible`
  - `growth-latent`
- add a new endogenous policy:
  - `self-selected`

The important architectural shift was:

- latent inference becomes structurally available but metabolically recruitable
- morphogenesis becomes structurally available but conditionally recruitable
- capability state is local and durable
- recruitment uses local signals such as ambiguity, contradiction, routing strain, ATP headroom, and carryover-supported usefulness

This moved capability choice from harness configuration into runtime substrate state.

### What worked

- `A1` became easy to keep clean during early tuning.
- `B2` and `C3` later improved substantially relative to the current-code local smoke oracle after the anticipation/carryover groundwork was added.
- prediction-aware capability state is now present before latent activation instead of only after the system is already reacting.

### What did not work yet

- the self-selected controller still does not reliably convert early evidence into the right capability/use regime on the hardest points
- `B2` and especially `C3` remained bottlenecked by how latent use affects actual transform choice
- later re-baselining showed that the local “oracle” can shift with code changes, which means smoke comparisons must be interpreted as current-code diagnostics, not as a replacement for the broader family map

### Current self-selected read

The current state is stronger than “trial and error only,” but weaker than “REAL now robustly chooses its own mode.” The system now senses and recruits earlier, but the selector often still fails to translate that into the right transform-family behavior.

---

## Thread 2: Anticipation Became a Real Core Concept

One of the most important architectural outcomes of the session was recognizing that the generalized REAL loop had a gap:

- memory was acting mostly as retrospective bias
- not yet as anticipatory structure for recognition and prediction

This led to a staged `real_core` update:

1. **Anticipation types and storage**
   - added `LocalPrediction` and `PredictionError`
   - threaded expectation recording into cycle/state handling

2. **Selector-facing anticipation**
   - added `SelectionContext`
   - added contextual selector support
   - added an anticipatory selector path that can use current-cycle expectations

3. **Recognition separated from prediction**
   - recognition became its own first-class step, not just a side effect of prediction
   - core loop direction became closer to:
     - `sense -> recognize -> predict -> select -> execute -> compare -> consolidate`

4. **Reusable pattern recognizer**
   - added a general pattern-based recognizer using durable substrate patterns

### Architectural significance

This was a real generalization improvement, not just a Phase 8 patch. `real_core` can now represent:

- what local situation looks familiar
- what local outcome is expected
- how wrong that expectation was

That creates a cleaner foundation for future domains, not just the current neural-substrate experiments.

---

## Thread 3: Recognition in Phase 8 Became Real and Safe

After anticipation support landed in `real_core`, Phase 8 was updated incrementally:

- first by wiring recognition into node construction without changing behavior
- then by allowing recognition to bias route choice slightly
- then by probing whether that bias actually appeared in transfer

The main recognition story across the session was:

1. **Recognition can now fire on durable Phase 8 substrate patterns.**
2. **Early transfer recognition initially failed because Phase 8 state and recognizer key spaces were misaligned.**
3. **Once the key-space mismatch was fixed, recognition appeared in real transfer paths.**
4. **Flat recognition bias could hurt near-tie choices.**
5. **Evidence-confirmation gating made recognition much safer.**

### Most important recognition conclusion

Recognition now works as a meaningful local prior, but it should not act as a free-standing command. The evidence-confirmation gate was the right theoretical move:

- recognized pattern + current local support -> useful bias
- recognized pattern + no support -> mostly quiet
- recognized pattern + contradiction -> damped

This kept the mechanism aligned with REAL’s local-accountability thesis.

### Practical outcome

Recognition became much safer and structurally present, but in lightweight sweeps it was usually neutral rather than clearly performance-improving. That is still a good result at this stage because it means anticipation can be added without destabilizing the system.

---

## Thread 4: Prediction in Phase 8 Became Observable and Causal

The next step was to move beyond recognition-only behavior and ask whether Phase 8 could actually predict.

That led to:

- a narrow `Phase8ExpectationModel`
- selector-facing predictive terms
- diagnostics for prediction timing and prediction/choice interaction
- prediction-aware benchmark probes

### What was established

- prediction is now present from cycle `1` in real Phase 8 runs on the tested benchmark slices
- prediction is not merely logged after the fact; it is now available before action selection
- prediction can affect route choice in some near-tie situations

### What was not established

- prediction is not yet the main source of improved early adaptation
- several predictive terms were initially too small or too overlapping with existing selector evidence
- the first “distinct prediction” attempt using stale-family risk did not light up in the main `A -> B` slice

### Best current interpretation

Prediction is now structurally real in Phase 8, but its direct behavioral leverage is still limited. In this session, prediction mostly acted as:

- a better diagnostic signal
- a stabilizing/nudging signal
- an earlier local input to capability pressure

rather than as the dominant driver of policy change.

---

## Thread 5: Time, Exposure, and Prediction

An earlier question was whether REAL simply needed more time.

That was tested in two forms:

- more idle runtime with the same experience stream
- more actual repeated exposure

### Result

- **More idle cycles did not help.**
- **More actual exposure did help.**

This held up after adding prediction instrumentation:

- repeated exposure generally strengthened prediction confidence and expected delta
- but the performance benefits were family-dependent

### Family-level pattern from the lightweight A/B/C probe

- `A1`: repeated exposure helped a lot
- `B2`: repeated exposure helped moderately
- `C3`: prediction strengthened somewhat, but performance improved only slightly

This matters because it suggests:

- the bottleneck is not “the system just needs more empty settling time”
- and on ambiguity-heavy multistate tasks, stronger anticipation alone still does not guarantee better behavior

---

## Thread 6: Carryover Hygiene Produced the Biggest Practical Gain

The strongest headline capability improvement of the session came from transfer/carryover work, not from prediction alone.

The key finding came from `B -> C`:

- `none` carryover outperformed `full` carryover on the early probe
- diagnosis showed stale carried context-transform structure strongly favoring `rotate_left_1`
- the stale bias lived largely in carried substrate structure, not just episodic memory

This led to a narrow cleanup strategy:

1. **Treat carried context-action/context-transform support more like a prior under mismatch.**
2. **Do not throw transfer away; instead make stale support discountable and challengeable.**
3. **Add visible-task compatibility so current task geometry can compete with stale carried priors.**

### Result

The second carryover pass was a real capability jump:

- warm `B -> C`, full carryover improved from:
  - `0.2222 -> 0.3889 -> 0.4444`
  - to `0.5556 -> 0.7500 -> 0.8148`
- warm `A -> C`, full carryover improved strongly as well
- `none` carryover stayed roughly unchanged

### Why this matters

This was exactly the right kind of improvement:

- it did **not** come from removing transfer
- it came from making transfer more selective and more locally challengeable
- it preserved the core REAL idea that durable structure should help future problems

This is one of the most important practical outcomes of the session.

---

## Thread 7: Re-Baselining Self-Selected After Anticipation and Carryover

After the anticipation and carryover work, the original `A1/B2/C3` self-selected slice was rerun.

### Result

Relative to the current-code local oracle:

- `B2` got much closer than it had been earlier
- `C3` also got much closer
- `A1` became the new outlier on that tiny slice

The more important diagnostic point was:

- source-side local evidence now appears before latent activation on `B2` and `C3`
- prediction is present from cycle `1`
- capability pressure is no longer operating in an evidence vacuum

So the self-selected problem is now narrower than before:

- not “the system cannot sense”
- not “the system cannot predict”
- not “the system cannot recruit”
- but “the system still does not always convert those capacities into the right transform/use regime”

---

## Thread 8: The `C3` Bottleneck Became Much More Specific

`C3` was the hardest and most revealing case.

Several passes pushed the diagnosis forward:

- prediction-coupled latent pressure made latent activation earlier
- uncertainty-weighted multistate context promotion gave a small gain without regressing binary tasks
- partial sequence persistence under partial multistate context did not improve self-selected `C3`
- direct comparison of `C3` `self-selected` vs `fixed-latent` finally clarified the gap

### Final `C3` diagnosis from this session

`fixed-latent` does not win because it has stronger latent confidence. It wins because it stays in a selector regime that remains aligned with the alternating XOR-family sequence hints.`

`self-selected` on the visible scenario does something different:

- it receives prediction early
- it eventually recruits latent capability
- but it still collapses toward a stable visible-path `context-0` / `rotate_left_1` attractor
- once that attractor has formed, latent activation does not pull transform competition back open

This is an important refinement. The remaining `C3` problem looks less like a sensing deficit and more like:

- a visible-scenario latent-use problem
- or an early regime-commitment problem inside selector/context dynamics

---

## Cross-Cutting Big-Picture Findings

### 1. REAL now has a credible anticipation architecture

Before this session, the repo had pieces that looked predictive. After this session:

- recognition is explicit
- prediction is explicit
- prediction error is explicit
- selectors can see current-cycle anticipation

This is a major conceptual improvement in the generalized REAL framework.

### 2. Self-selection is closer to viable, but not solved

The self-selected controller is now much better scaffolded:

- richer local evidence
- earlier prediction
- prediction-coupled latent pressure
- better carryover substrate beneath it

But the remaining difficulty is now selector/use quality under ambiguity, not raw recruitment or observability.

### 3. Transfer remains one of REAL’s strongest differentiators

The session reinforced rather than weakened the original thesis:

- carryover is a real source of competence
- it can outperform no-carryover substantially
- but it must be challengeable rather than treated as absolute truth

This is exactly the kind of robustness advantage REAL is supposed to have over conventional training-only systems.

### 4. Multi-context ambiguity still exposes the deepest architectural questions

The user’s caution about not collapsing C-family behavior back to binary was exactly right. The hardest failures are not on binary visible tasks; they are on ambiguity-heavy multistate tasks where:

- evidence streams conflict
- context should remain uncertain longer
- and selector regimes matter more than raw signal presence

That means future work on REAL’s broader generalization should likely stay centered on multistate ambiguity, not only easier visible-family slices.

---

## Key Updates

### Architectural updates

- `real_core` now supports recognition, prediction, prediction error, and selector-facing anticipation.
- Phase 8 now uses a real expectation binding, not only retrospective scoring.
- benchmark probes and transfer harnesses now expose anticipation metrics directly.

### Behavioral updates

- recognition can fire in real transfer paths and bias selection safely when evidence-confirmed
- prediction fires from the beginning of benchmark/transfer runs
- repeated experience strengthens prediction more than idle runtime does
- carryover hygiene plus visible-task compatibility produced large improvements on `B -> C` and `A -> C`

### Diagnostic updates

- self-selected capability control is now prediction-aware
- benchmark node probes can now show whether prediction precedes latent recruitment
- `C3` now has a much more precise failure description than earlier in the session

---

## Key Findings

1. **Anticipation belongs in `real_core`, not only in Phase 8.**
2. **Recognition as a prior works best when gated by current evidence.**
3. **Prediction is real in Phase 8 now, but not yet the dominant adaptation driver.**
4. **More exposure helps; more idle time does not.**
5. **Carryover is highly valuable, but stale carried structure must be challengeable.**
6. **The current hardest gap is not capability recruitment itself; it is how self-selected latent use changes transform-family competition on multistate ambiguous tasks.**

---

## Open Questions

1. **Visible-path `C3` regime problem**
   - Why does the visible self-selected path stabilize toward `context-0 / rotate_left_1` so early?
   - Which selector or latent-estimate mechanism is responsible for that regime lock-in?

2. **Latent use vs latent recruitment**
   - What specific selector terms need to change so that latent activation actually reopens transform-family competition rather than arriving too late to matter?

3. **Prediction’s best leverage point**
   - Is the next useful predictive signal about branch-switch value, ambiguity persistence, transform-family volatility, or something else entirely?

4. **Self-selected re-baselining on richer slices**
   - If the improved carryover/anticipation baseline is carried back into a broader but still lightweight A/B/C comparison, does the self-selected family pattern begin to align more closely with the original task-family map?

5. **Multi-context generalization**
   - Can self-selected REAL preserve multistate uncertainty longer without sacrificing the strong transfer gains recovered in the carryover passes?

6. **Transfer as anticipatory substrate**
   - To what extent are the recent gains really “prediction gains,” and to what extent are they better transfer priors plus better local contradiction handling?

---

## Suggested Next Step

The best next move is probably not another broad new mechanism.

It is a focused `C3`-centered pass on **latent use after activation** in the visible self-selected path, using the current stronger carryover/anticipation baseline. That is now the clearest remaining bottleneck if the goal is still:

> REAL should learn when and how to use its own capabilities rather than being told which mode to run.
