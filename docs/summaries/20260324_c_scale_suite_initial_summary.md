# 20260324 C Scale Suite Initial Summary

## Scope

This note summarizes the first dedicated C-family scale results from the new
`compare_c_scale_suite.py` harness.

The chosen lane fixes the original `C3` ambiguity structure and scales topology
and horizon through generated `C3S5` and `C3S6` points:

- `C3S5`: 75 nodes, 432 examples
- `C3S6`: 100 nodes, 864 examples

The focus here is cold-start behavior on `task_a`, not transfer or carryover.

## Why This Matters

The March 18 ceiling work already suggested that the late C family was limited
more by observation identifiability than by raw scale. The question for the new
scale suite was whether larger ambiguous tasks would:

- stay flat across all modes
- reveal a stronger latent path
- or recover a visible-growth advantage the way A-family sometimes does

## Results

### `C3S5`

| Method | Exact match rate | Bit accuracy | Criterion | Elapsed |
|---|---:|---:|---:|---:|
| `fixed-visible` | **0.2940** | 0.5625 | 0.0 | 51.7s |
| `fixed-latent` | 0.2755 | **0.5694** | **1.0** | **43.2s** |
| `growth-visible` | 0.2731 | 0.5486 | 0.0 | 128.6s |
| `growth-latent` | 0.2685 | 0.5648 | **1.0** | 108.5s |

Read:

- all four REAL modes stayed in roughly the same weak band
- latent was slightly better on bit accuracy and short-window criterion
- growth did not help and added substantial cost

### `C3S6`

| Method | Exact match rate | Bit accuracy | Criterion | Elapsed |
|---|---:|---:|---:|---:|
| `fixed-latent` | **0.3345** | 0.5012 | 0.0 | **103.8s** |
| `growth-visible` | 0.2083 | **0.5255** | 0.0 | 340.2s |
| `fixed-visible` | 0.1667 | 0.5145 | 0.0 | 137.1s |

Read:

- `fixed-latent` separated clearly on exact-match rate
- visible modes remained weak, with `growth-visible` only modestly better than
  `fixed-visible` despite a very large runtime cost
- no method reached criterion at this larger ambiguity-heavy point

## Interpretation

The C-scale lane now has a distinct identity relative to A and B.

### 1. Ambiguity remains the dominant bottleneck

Unlike A-family, larger topology and horizon do not produce a generally stronger
visible or growth-visible path. The main challenge still appears to be weak
observability rather than raw capacity.

### 2. Latent becomes more important as scale increases

At `C3S5`, visible and latent were nearly tied. At `C3S6`, `fixed-latent`
substantially outperformed `fixed-visible` on exact-match rate. That suggests
the latent path may become the more appropriate mode as ambiguous tasks get
larger, even though the regime is still weak overall.

### 3. Growth is not a general rescue mechanism for C-family scale

Growth was expensive at both points and did not unlock an A-style quality jump.
That supports the earlier C-family diagnostic hypothesis: morphogenesis helps
more with routing-headroom problems than with identifiability problems.

## Cross-Family Takeaway So Far

The first large-point scale picture now looks like this:

- A-family:
  - scale alone is comparatively friendly
  - `growth-visible` can be the best-quality mode
- B-family:
  - scaling depends strongly on hidden-memory depth
  - visible modes remain strongest, but which visible mode wins can flip
- C-family:
  - ambiguity remains the main limiter
  - latent becomes more competitive, and by `C3S6` it is clearly best on exact
    match among the tested modes

This is a useful result for the broader scale question. REAL does not appear to
have one single scaling story. The mode that scales best depends strongly on
what kind of difficulty is being scaled.

## Practical Read

On consumer hardware, the C-family lane is still runnable at aspirational points,
but the return on additional cost is much weaker than on A-family:

- `C3S5` remained within about `43-129s`
- `C3S6` stretched to about `104-340s`

So the system scales operationally into these larger ambiguous settings, but the
performance story is currently "still coherent, still difficult" rather than
"larger scale reveals a stronger overall solution."

## Recommended Next Step

If C-family work continues before cross-family comparison, the most informative
next experiment would be one of:

1. a 2-seed `C3S6` visible vs latent confirmation
2. a transfer-inclusive `C3S5/C3S6` check focused on the latent path
3. a separate `C4`-style lane only after the `C3` ambiguity scale story is
   considered stable enough to compare against a harsher scrambled-visible regime
