## 2026-03-30 1454 - ATP Budget Headroom for C HR Pilot

### Why

After inspecting `C3S2`, a recurring pattern appeared:

- growth requests were live
- candidate targets existed
- but early-layer nodes often had very low `atp_ratio` and near-zero `energy_surplus`

That meant the system was structurally willing to grow but metabolically unable to afford the proposals. The current pilot had no clean way to raise node ATP capacity without changing Phase 8 defaults globally.

### Changes

Added explicit ATP-budget plumbing for laminated pilots:

- `phase8/lamination.py`
  - `build_system_for_scenario(..., max_atp=...)`
  - `evaluate_laminated_scenario(..., max_atp=...)`
  - fast-state snapshot / restore and mode-switch rebuilds now preserve `max_atp`
- `phase8/environment.py`
  - runtime export/load now includes environment-level `max_atp`
  - this matters because newly created dynamic nodes inherit `environment.max_atp`
- `scripts/evaluate_laminated_phase8.py`
  - added `--max-atp`
- `scripts/evaluate_hidden_regime_forecasting.py`
  - added `--max-atp`

### Validation

Focused tests passed:

- `python -m unittest tests.test_phase8_lamination tests.test_latent_growth_gate tests.test_lamination`

Added coverage:

- `tests/test_phase8_lamination.py`
  - mode-switch rebuild preserves elevated `max_atp`

### First read with `max_atp = 2.0`

Pilot setup:

- overlap topology: `bounded_overlap_13715`
- local unit mode: `pulse_local_unit`
- preset: `c_hr_overlap_tuned_v1`
- seed `13`
- budget `6`
- safety limit `40`

CLI compact results:

- `C3S2 task_a`: `0.557 -> 0.593`
- `HR2 task_a hidden`: `0.800 -> 0.875`

Growth-side inspection:

- `C3S2`
  - `max_requesting_nodes = 2`
  - `max_pending_proposals = 1`
  - still `0` active growth nodes
- `HR2`
  - `max_requesting_nodes = 7`
  - `max_pending_proposals = 1`
  - `max_active_growth_nodes = 1`
  - still reaches `initiate`

### Interpretation

Raising ATP headroom appears helpful for the current combined pilot. It improves benchmark outcomes and gives the system a bit more room to carry growth requests into proposal generation.

But it does not fully solve visible C-family growth. The remaining issue is not simply “too little ATP” anymore. It is more likely a combination of:

- proposal viability
- queue-window timing
- and when struggling nodes get slow-layer authorization relative to their local state
