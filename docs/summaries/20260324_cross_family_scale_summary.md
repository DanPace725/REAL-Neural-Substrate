# 20260324 Cross-Family Scale Summary

## Scope

This note summarizes the first dedicated scale work across the new A-, B-, and
C-family harnesses.

The goal is not to claim that REAL has one simple scaling curve. The goal is to
state as clearly as possible what the current repo actually shows when topology
and horizon are pushed to larger points on consumer hardware.

The relevant harnesses are:

- `scripts/compare_a_scale_suite.py`
- `scripts/compare_b_scale_suite.py`
- `scripts/compare_c_scale_suite.py`

## What Each Family Is Scaling

### A-family

A-family is the cleanest scale lane. It mostly asks:

- if topology and horizon increase
- while the task remains comparatively clean and visible
- does REAL stay coherent, and which mode works best?

### B-family

B-family adds hidden-memory dependence. It asks:

- can REAL still scale when the correct transform depends on a latent sequential
  state rather than only the current visible input?

The important detail is that B scaling is lane-specific:

- `B2`: parity over previous 2 packets
- `B8`: parity over previous 8 packets

### C-family

C-family scales an ambiguity-heavy lane. It asks:

- what happens when topology and horizon increase
- but the visible context is not a reliable identifier of the transform?

So C is less about raw routing headroom and more about identifiability under scale.

## Largest Points Tested So Far

| Family | Benchmark | Nodes | Examples | Main condition tested |
|---|---:|---:|---:|---|
| A | `A6` | 100 | 864 | clean visible scale |
| B2 | `B2S6` | 100 | 864 | moderate hidden-memory scale |
| B8 | `B8S6` | 100 | 864 | deep hidden-memory scale |
| C | `C3S6` | 100 | 864 | ambiguity-heavy scale |

## Best Current Results By Family

### A-family cold-start

At the larger clean scale points, `growth-visible` is currently the best quality
mode:

- `A5`: exact `0.8542`, bit accuracy `0.9062`, mean elapsed `118.3s`
- `A6`: exact `0.7188`, bit accuracy `0.8339`, elapsed `310.7s`

`fixed-visible` remains the best practical lower-cost option:

- `A6`: exact `0.5845`, bit accuracy `0.7564`, elapsed `118.7s`

### B-family cold-start

There is no single B-family winner.

For `B2`:

- `B2S6 fixed-visible`: exact `0.8079`, bit accuracy `0.8854`, elapsed `108.7s`

For `B8`:

- `B8S6 growth-visible`: exact `0.3160`, bit accuracy `0.5961`, elapsed `577.9s`
- `B8S6 fixed-visible`: exact `0.1794`, bit accuracy `0.5451`, elapsed `261.6s`

So moderate hidden-memory scale and deep hidden-memory scale behave very differently.

### C-family cold-start

At the larger ambiguity-heavy point, `fixed-latent` is currently the strongest
mode on exact match:

- `C3S6 fixed-latent`: exact `0.3345`, bit accuracy `0.5012`, elapsed `103.8s`

Visible modes remain weaker there:

- `C3S6 growth-visible`: exact `0.2083`, bit accuracy `0.5255`, elapsed `340.2s`
- `C3S6 fixed-visible`: exact `0.1667`, bit accuracy `0.5145`, elapsed `137.1s`

### C-family transfer

The first transfer-inclusive C result is on `C3S5 task_a -> task_c`:

- `fixed-visible`
  - cold: `0.3866 / 0.5938`
  - warm: `0.4375 / 0.6424`
  - delta: `+0.0509 / +0.0486`
- `fixed-latent`
  - cold: `0.3380 / 0.5810`
  - warm: `0.1806 / 0.4132`
  - delta: `-0.1574 / -0.1678`

This is important because it shows that C-family transfer is not just a replay of
cold-start scaling. Visible carryover helped, while latent carryover hurt.

## Cross-Family Comparison

| Family | Best current mode | What scales well | What breaks first |
|---|---|---|---|
| A | `growth-visible` for quality, `fixed-visible` for practicality | clean visible scale | runtime cost starts separating by `A6` |
| B2 | `fixed-visible` | moderate hidden-memory scale | growth becomes unreliable |
| B8 | weak overall, `growth-visible` better than `fixed-visible` at `B8S6` | some recovery under hard memory pressure | quality degrades sharply and cost becomes very high |
| C cold-start | `fixed-latent` at `C3S6` | latent competitiveness under ambiguous scale | visible supervision signal stays weak |
| C transfer | `fixed-visible` so far | useful visible carryover on ambiguity lane | latent carryover can become actively harmful |

## Current Claims We Can Defend

### 1. REAL does not have one universal scaling story

This is probably the most important conclusion from the current work.

- A-family is relatively friendly to scale
- B-family is highly sensitive to hidden-memory depth
- C-family is dominated by ambiguity and path dependence

So the right question is not "does REAL scale?" in the abstract. The better
question is "what kind of difficulty is being scaled, and which REAL mode is
compatible with that difficulty?"

### 2. Scale alone is not currently REAL's clearest failure axis

A-family remains strong through `100` nodes / `864` examples, and even the harder
families remain operationally coherent at those sizes.

The current evidence points more strongly toward:

- hidden-memory depth
- ambiguity / weak observability
- and runtime cost

as the sharper near-term constraints.

### 3. Growth is useful, but only in some regimes

Growth is not a universal win or loss.

- On A-family, it can be the best quality mode
- On B2, it can help at intermediate scale but lose badly later
- On B8, it can recover some capability at the hardest point, but expensively
- On C cold-start, it is not a strong rescue path

So the current evidence supports treating morphogenesis as regime-dependent rather
than as a general-purpose scaling fix.

### 4. Latent mode is also regime-dependent

Latent mode is not simply "harder but better."

- On A, it is weaker than visible
- On B, it is clearly behind visible in cold-start scaling
- On C cold-start, it becomes the most competitive mode at the larger point
- On C transfer, latent carryover can become harmful

That means latent support is promising, but not yet stable across different uses.

### 5. Consumer-hardware runtime is substantial, but not absurd for what REAL is doing

The current scale runs are not cheap, but they are also not obviously unreasonable
for a pure-Python local-adaptation substrate experiment:

- many strong A/B/C points remain in the `40s` to `140s` band
- the heavier points move into the `300s` to `580s` band
- the first wide C transfer slice was heavy enough to hit a 30-minute timeout

So the honest runtime story is:

- slower than conventional small-task neural training
- still workable for research iteration
- increasingly expensive once ambiguity, memory depth, or transfer are layered in

## What Still Feels Fuzzy

There are still several important uncertainties:

- A-family transfer at larger points has not been mapped in the same scale-specific way
- B-family transfer has not yet been carried through the new scale harnesses
- C-family transfer has only one confirmed seed so far
- `self-selected` has not shown competitive scale behavior yet
- the scale suites currently reach aspirational consumer-hardware points, but not
  a true "large-system" regime beyond that

## Recommended Next Steps

If the goal is to strengthen the scaling story before adding more families, the
highest-value follow-ups are probably:

1. confirm `C3S5 task_a -> task_c` visible vs latent transfer with a second seed
2. add one short cross-family comparison figure from these summaries
3. decide whether the next scale effort should prioritize:
   - transfer across A/B/C, or
   - pushing one family beyond the current `100`-node / `864`-example band

## Bottom Line

The current repo now supports a more precise scaling claim:

REAL scales meaningfully on several task families into the `100`-node /
`864`-example range on consumer hardware, but the best mode depends strongly on
what is being scaled. Clean visible scale, hidden-memory scale, and ambiguity
scale do not behave the same way, and the main limitations currently look more
like memory depth, ambiguity, carryover alignment, and runtime cost than like a
single generic collapse under size alone.
