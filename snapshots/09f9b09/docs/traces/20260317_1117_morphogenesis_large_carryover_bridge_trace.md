# 2026-03-17 1117 - Large-Topology Carryover Bridge Diagnostic

**Type:** H_e (Experiment trace)
**Harness:** `compare_morphogenesis_large_carryover_bridge.py`
**Output artifact:** `docs/experiment_outputs/20260317_1113_morphogenesis_large_carryover_bridge.json`

**Seeds:** 13, 23, 37, 51, 79
**Setting:** `A large -> B large` transfer with morphogenesis
**Policies:** `all_visible`, `all_latent`, `visible_train_latent_transfer`
**Carryover modes:** `full`, `substrate`

---

## 1. Headline result

The old warm-vs-substrate distinction is directly relevant here. It changes the story substantially.

### Aggregate transfer deltas

| Policy | Full carryover | Substrate-only carryover |
|---|---:|---:|
| all visible | +2.2 exact, +0.0417 bit acc | +6.0 exact, +0.1305 bit acc |
| all latent | +7.0 exact, +0.1472 bit acc | -2.2 exact, -0.0356 bit acc |
| visible train -> latent transfer | -2.0 exact, -0.0778 bit acc | +3.2 exact, +0.0584 bit acc |

---

## 2. What changed

### Visible path

- Substrate-only improved visible transfer strongly:
  - `+6.0` exact vs `+2.2` with full carryover
  - `+0.1305` bit accuracy vs `+0.0417`

This strongly suggests that some of the visible-path transfer drag does live in full episodic carryover rather than in structural substrate alone.

### Latent path

- Substrate-only collapsed the latent advantage:
  - `-2.2` exact vs `+7.0` with full carryover
  - `-0.0356` bit accuracy vs `+0.1472`

So latent success here depends on more than bare substrate persistence. Whatever is being removed by substrate-only carryover is important to latent transfer.

### Switched visible->latent path

- Full carryover was clearly bad: `-2.0` exact
- Substrate-only rescued it to `+3.2` exact

This means the naive mode-switch failure was not purely a fixed architectural incompatibility. A large part of the failure does seem to come from what full carryover brings forward.

---

## 3. Important nuance

In this repo, `substrate-only` does **not** mean edge-only.

It removes node episodic entries, but still preserves system-level state such as topology, admission substrate, latent context trackers, and task-seen regime metadata. So this bridge diagnostic isolates episodic carryover effects more than it isolates all context-related state.

That makes the result sharper:

- the visible-to-latent handoff problem is at least partly episodic
- but latent full carryover still dominates latent substrate-only, so latent transfer also needs some nontrivial carried state beyond bare substrate supports

---

## 4. Best current policy reading

The best policies after this bridge test are:

1. **all latent with full carryover**: strongest overall transfer (`+7.0`)
2. **all visible with substrate-only carryover**: strong second-place result (`+6.0`)
3. **visible train -> latent transfer with substrate-only carryover**: rescued and positive (`+3.2`), but not best

So the bridge helps, but it does not make the mixed policy win.

---

## 5. Next step

The next narrow experiment should be more surgical than simple substrate-only carryover:

- **edge-only or topology-only bridge** for visible->latent handoff
- or **substrate-only plus latent warm-up** before enabling full transfer evaluation

The present result says:

- full carryover is too much for the visible->latent switch
- substrate-only removes too much for all-latent
- the winning bridge likely sits between those two extremes
