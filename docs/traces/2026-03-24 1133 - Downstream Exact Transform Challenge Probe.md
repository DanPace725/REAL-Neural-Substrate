# 2026-03-24 1133 - Downstream Exact Transform Challenge Probe

## Intent

After the downstream selector read, the most tempting intervention was to give
non-source visible-context nodes a small exact-transform nudge.

The hypothesis was:

- the current selector already knows the task family
- but downstream branch nodes may still need a local push toward the exact
  expected transform under explicit visible context

## Probe

Tried a branch-node-local selector pass that:

- added exact visible transform affinity into local observation
- rewarded the exact expected transform on downstream visible nodes
- penalized same-family but wrong exact transforms

Also added a regression proving a downstream node could prefer the exact visible
transform over a stale same-family alternative.

## Validation

The selector and diagnostic tests passed under the probe configuration.

Executed:

- `python -m unittest tests.test_phase8_recognition tests.test_b_to_c_visible_timecourse`

## Rerun

Executed:

- `python -m scripts.analyze_b_to_c_visible_timecourse --seeds 23 37 --modes none full full_context_actions_scrubbed full_context_scrubbed --output docs/experiment_outputs/2026-03-24_b_to_c_visible_timecourse_23_37_postdownstream.json`

Saved artifact:

- `docs/experiment_outputs/2026-03-24_b_to_c_visible_timecourse_23_37_postdownstream.json`

## Result

The probe was **too blunt**.

It did fix the seed `37` downstream trap:

- `full`: `18 exact / 1.0 bit / 1.0 ctx1 bit`

But it also collapsed the useful separation on seed `23`:

- `full`: `10 exact / 0.5556 bit / 0.0 ctx1 bit`
- `full_context_actions_scrubbed`: same
- `full_context_scrubbed`: same

So instead of clarifying the carryover composition story, the intervention
mostly flattened it.

That is a bad sign because the earlier bridge and timecourse results were
telling us that:

- seed `23` and seed `37` fail for different reasons
- and the mode split itself is informative

The exact-transform nudge improved one failure mode by bulldozing the structure
that made the other one legible.

## Decision

Reverted the selector/environment change after the probe.

Kept:

- the downstream selector diagnostic extensions in
  `scripts/analyze_b_to_c_visible_timecourse.py`
- the experiment artifact
- this trace

Did **not** keep:

- the exact visible downstream transform intervention itself

## Interpretation

This was a useful negative result.

The downstream hotspot is real, but the right intervention is probably not a
generic exact-transform reward for all visible downstream nodes.

That kind of rule is too architecture-external and too broad relative to the
seed-specific failure patterns we are actually seeing.
