# 2026-03-31 0005 - C Layer 1 Communication Scaffold and Threshold Guard

## Why

The visible C-family runs were still behaving like they had a hard ceiling around `.5-.6`, even after:

- overlap topology
- pulse local units
- stronger graph structure
- a slower world-model Layer 3 pilot

The main question was no longer just "can the system infer the right latent state?" It became:

- if we give the system better latent support, why does it still fail?
- is the real bottleneck in Layer 1 execution and preservation?
- are some of the apparent wins just artifacts of controller thresholds or tiny early slices?

This pass treated the current architecture like a high-assistance mockup:

- force or guide missing structure
- watch where the system breaks anyway
- then work backward toward the smallest endogenous mechanism that explains the gain

## Main Passes

### 1. Added a controller-level Layer 3 world-model pilot

Implemented a slow world-model layer in `real_core/world_model.py` and integrated it through laminated control and Phase 8 carryover/runtime state.

The pilot tracks:

- a 5-slot hypothesis field (`h0..h3`, `unknown`)
- support / contradiction / revisit / dead-end / transition state
- a summary-safe `world_model_summary` on slice metadata and regulatory metadata

Initial result:

- Layer 3 was live and persistent
- it changed Layer 2 control behavior
- but it did not materially improve the hard C runs by itself

Strong assistance from Layer 3 actually hurt until commit pressure was removed. Once strong assist was changed to mostly preserve ambiguity and bias reopening, the damage disappeared, but performance still did not improve.

Interpretation:

- the bottleneck was no longer mainly "missing world model"
- the bottleneck was how Layer 1 cashes out context into action

### 2. Added assisted world-model modes and found the handoff bottleneck

Implemented `hinted`, `guided`, and `teacher` assistance modes for Layer 3.

On `C3S2 / task_a / visible` with overlap + pulse:

- light hinting was mostly harmless but not useful
- strong assisted commit hurt badly
- changing teacher/guided to "hold open only" removed the regression but did not improve the task

Interpretation:

- correct abstract context alone does not rescue the task
- the context-to-action coupling in Layer 1 is weak or broken

### 3. Added sink forcing and then teacher-trace forcing

First, a sink-only forced-transform diagnostic was added.

That showed:

- forcing the correct final transform rarely rescued errors
- the packet was usually already wrong before the sink

Then a `teacher_trace` mode was added with staged forcing:

- `observe`
- `force_source`
- `force_source_l1`
- `force_source_l1_l2`
- `force_all`

On `C3S2 / task_a / visible`, 10-slice teacher-trace runs showed a very clear pattern:

- without forcing, first divergence often starts at `n0`
- if the source is forced correct, divergence moves downstream
- if source + early layer are forced, divergence moves deeper again
- only forcing essentially the whole path reliably rescues the task

Interpretation:

- the failure is distributed through Layer 1
- the source is a major failure point, but not the only one
- downstream nodes do not reliably preserve a correct intermediate computation

### 4. Added a dedicated C-task Layer 1 stabilization scaffold

A strong `stabilized` Layer 1 mode was added for C tasks. This mode effectively:

- resolves the critical transform early
- carries the resolved transform on the packet
- biases downstream nodes to preserve with `identity`

This was a heavy assist, closer to guided execution than an endogenous mechanism, but it answered the core question.

Key result on `C3S2 / task_a / visible`, overlap + pulse, seed `13`:

- `legacy @ max_atp=2.0`: about `0.603`
- `stabilized @ max_atp=2.0`: about `0.737`
- `legacy @ max_atp=2.5`: about `0.536`
- `stabilized @ max_atp=2.5`: about `0.826`

Interpretation:

- the current architecture can do much better on C when Layer 1 follows "resolve once, preserve after"
- the missing capability is not raw power, but execution discipline

### 5. Replaced the hard scaffold with a softer communicative Layer 1 mode

To move toward an endogenous mechanism, the hard scaffold was softened into a packet-level communication system.

Added packet signals for:

- `resolution_confidence`
- `preserve_pressure`
- `reopen_pressure`

The new `communicative` mode lets nodes write and read those signals and bias preserve / reopen without hard-pruning the full action space.

This carried a large fraction of the stabilization gain:

- `legacy @ max_atp=2.0`: about `0.603`
- `communicative @ max_atp=2.0`: about `0.750`
- `stabilized @ max_atp=2.0`: about `0.737`

- `legacy @ max_atp=2.5`: about `0.536`
- `communicative @ max_atp=2.5`: about `0.719`
- `stabilized @ max_atp=2.5`: about `0.826`

Interpretation:

- packet-level preserve / reopen communication is real signal, not noise
- a large part of the missing capability is inter-node epistemic communication

### 6. Tuned communicative mode toward endogenous self-hardening

Several follow-up passes pushed communicative mode toward stronger but still soft execution discipline:

- self-hardening when preserve pressure is high and reopen is low
- higher reopen cost
- stronger preserve retention
- confidence-sensitive hardening

The most useful improvement was confidence-sensitive hardening.

On `C3S2 / task_a / visible`, overlap + pulse, world model off:

- `communicative @ max_atp=2.5`: improved from about `0.763` to about `0.789`
- `communicative @ max_atp=2.0`: improved from about `0.714` to about `0.761`

The world model still added nothing in this regime.

Interpretation:

- Layer 1 communication/execution is doing the meaningful work here
- Layer 3 remains secondary on these runs

### 7. Compared task families and found the asymmetry again

The strong `gradient` configuration on `C3S2 / task_a / visible` looked excellent:

- `final=0.917` in compact output for one notable run

But switching only the task to `task_c` looked like a collapse in compact mode.

After saving full JSON runs and inspecting them carefully, the picture was subtler:

- compact `final=` only reports the last slice, not the whole run
- `task_c final=0.000` happened because the last slice evaluated zero packets
- full-run mean bit accuracy remained strong

Artifacts:

- `tests_tmp/task_a_gradient_225_routes.json`
- `tests_tmp/task_c_gradient_225_routes.json`

Key findings:

- both tasks stayed similar through roughly slices `1-8`
- the split appeared later, around slices `9-10`
- both tasks were strong on `context_1`
- both tasks were weaker on `context_0`
- `task_c` was worse on the weak branch

End-of-run context breakdown:

- `task_a`: `context_0 = 0.6541`, `context_1 = 0.8738`
- `task_c`: `context_0 = 0.5915`, `context_1 = 0.8906`

Final source supports diverged sharply:

- `task_a` source supports stayed balanced
- `task_c` source supports collapsed onto `n3`

Interpretation:

- this is the same asymmetry family seen in older traces
- the weak branch is still `context_0`
- `task_a` is easier because its transform families are more separable
- `task_c` asks the system to maintain a harder xor-vs-xor distinction under preserve-heavy dynamics

### 8. Investigated misleading one-slice settles under `learning`

Running:

- `--reg learning`
- `--budget 12`
- `--max-atp 2`
- `--thresh .8`

caused both `task_a` and `task_c` to appear to solve instantly:

- `final=1.000`
- `slices=1`
- `[settle]`

Saved outputs showed why:

- each run only evaluated 2 packets on slice 1
- both happened to be correct
- threshold settlement was allowed with only one slice

The `learning` regulator was not doing anything special here. It delegates terminal decisions to the heuristic regulator unchanged.

## Fix Applied

Patched the heuristic threshold settlement rule in `real_core/lamination.py` so explicit threshold settlement now requires at least 2 slices.

Added focused test coverage in `tests/test_lamination.py`.

After the patch, the same `learning` configuration behaved realistically:

- `task_a`: `final=0.773`, `slices=40`, `[continue]`, `context_0=0.69`, `context_1=0.89`
- `task_c`: `final=0.765`, `slices=40`, `[continue]`, `context_0=0.62`, `context_1=0.89`

Interpretation:

- the one-slice solve was a threshold loophole, not real competence
- once removed, the same weak-context asymmetry reappears

## What This Pass Changed Conceptually

The strongest conclusion from the day is:

- the current C-family bottleneck is primarily in Layer 1

More specifically:

- nodes do not naturally know when to transform versus preserve
- correct intermediate computation is not reliably protected across hops
- downstream nodes keep renegotiating packets instead of preserving resolved state

The strongest endogenous-looking clue so far is:

- packet-level communication about epistemic status matters

Not "I know I am correct," but something like:

- I have high resolution confidence
- preserve this unless contradiction rises
- reopen only when pressure is high enough

That communication mechanism appears to be a much better fit for the observed gains than the earlier idea that the main missing ingredient was a strong controller-level world model.

## Files Touched Across This Pass

Main areas touched:

- `real_core/world_model.py`
- `real_core/lamination.py`
- `phase8/environment.py`
- `phase8/lamination.py`
- `phase8/models.py`
- `phase8/adapters.py`
- `phase8/selector.py`
- `scripts/evaluate_laminated_phase8.py`
- `tests/test_world_model.py`
- `tests/test_phase8_lamination.py`
- `tests/test_phase8_world_model_carryover.py`
- `tests/test_lamination.py`

## Validation Highlights

Focused test suites passed at different stages, including:

- `python -m unittest tests.test_world_model tests.test_lamination tests.test_phase8_lamination tests.test_phase8_world_model_carryover`
- `python -m unittest tests.test_lamination`

## Open Tasks

### 1. Move from packet hack to node-native adaptive state

The current communicative gains still rely heavily on packet-level task fields. The likely next architectural step is to move more of this into node-local adaptive state:

- dominant transform hypothesis
- transform confidence
- preserve / reopen regime
- contradiction load
- commitment age

### 2. Improve weak-context rescue

`context_0` is still the weak branch in the better C runs. We still need a clearer mechanism for:

- weak-branch protection
- source support recovery
- differentiating similar transform families under preservation

### 3. Better xor-family differentiation

`task_c` appears harder because it relies on distinguishing xor families rather than rotate-vs-xor. This likely needs:

- stronger local transform discrimination
- less collapse into a single preserved attractor
- better preservation of early differentiating evidence

### 4. Finish the node redesign implied by the RNA / local-code idea

The redesign notes already gestured at splitting node state into:

- signal
- context / ambiguity
- plasticity / growth

We partially aligned with that, but the communicative path still lives halfway between packet metadata and true node-native adaptive code.

### 5. Revisit graph-native slow layers later

Layer 2 and Layer 3 are still controller-native, not graph-native. That remains an architectural gap, but after this pass it no longer looks like the first-order blocker for visible C competence.

### 6. Add better per-slice source diagnostics

The current source-route breakdown was useful, but the next useful instrumentation is probably:

- context -> chosen source transform by slice
- context -> chosen source branch by slice
- source support change by slice
- explicit weak-branch reinforcement / starvation metrics

## Bottom Line

The most important result from this trace is not just that C-family visible runs moved past the old `.6` region. It is that we now have a much clearer picture of why:

- a heavy Layer 1 "resolve then preserve" scaffold works
- a softer communicative preserve / reopen scaffold also works
- controller-level world modeling does not help much unless Layer 1 can already preserve a correct computation

That gives a much more concrete target for the next passes: not "make the controller smarter," but "make Layer 1 communicate and preserve resolved state endogenously."
