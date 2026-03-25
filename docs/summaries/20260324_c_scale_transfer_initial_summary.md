# 20260324 C Scale Transfer Initial Summary

## Scope

This note summarizes the first transfer-inclusive result from the dedicated
C-family scale harness.

Setup:

- benchmark: `C3S5`
- train task: `task_a`
- transfer task: `task_c`
- seed: `13`
- methods:
  - `fixed-visible`
  - `fixed-latent`

The question was whether carryover helps or hurts transfer on the new ambiguity
scale lane.

## Results

| Method | Cold exact / bit | Warm exact / bit | Warm delta vs cold |
|---|---:|---:|---:|
| `fixed-visible` | `0.3866 / 0.5938` | `0.4375 / 0.6424` | `+0.0509 / +0.0486` |
| `fixed-latent` | `0.3380 / 0.5810` | `0.1806 / 0.4132` | `-0.1574 / -0.1678` |

Additional notes:

- `fixed-visible` reached criterion in both cold and warm transfer, with stronger
  best rolling performance in the warm case
- `fixed-latent` failed to reach criterion in both cases and became much worse
  under carryover

## Technical Read

This is the first clear evidence in the new C-family scale lane that transfer is
not behaving like cold-start scaling.

### Visible carryover can still help

On `C3S5`, warm visible transfer from `task_a -> task_c` improved both exact-match
rate and bit accuracy relative to the cold visible baseline.

### Latent carryover can be harmful

On the same point, warm latent transfer was substantially worse than cold latent.
So the current C-family transfer story is not "latent solves ambiguity." It is
more conditional: latent can become more competitive on cold-start larger points,
but stored latent carryover may mismatch the next ambiguous task and degrade it.

### C-family is more path-dependent than A-family

The C lane now looks strongly sensitive to how the substrate is prepared before
evaluation, not just to the size of the topology or the presence/absence of a
visible context bit.

## Working Conclusion

The first C-family transfer slice suggests:

- ambiguity remains the dominant limiter
- visible carryover can still give a modest but real gain
- latent carryover is not safely reusable across ambiguous tasks and may need
  additional gating, reset discipline, or task-sensitive recruitment

## Recommended Next Step

The next best confirmation run is a second-seed `C3S5 task_a -> task_c` visible
vs latent transfer check before scaling the transfer slice up to `C3S6`.
