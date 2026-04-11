# 2026-03-18 1200 - Ceiling Benchmark Harness

## Purpose

This trace records the first implementation pass of the paper-oriented ceiling-mapping benchmark suite. The goal is to freeze a consistent benchmark surface before tuning REAL, so the first observed collapse band is measured rather than optimized away in advance.

## What Was Added

- A deterministic benchmark suite with three monotonic families:
  - `A1-A4` for scale / horizon growth
  - `B1-B4` for hidden-memory depth
  - `C1-C4` for transform ambiguity
- A reduced transfer slice selection rule driven by the measured frontier:
  - easiest anchor
  - one pre-ceiling point
  - one post-ceiling point
- A new comparison harness that aggregates over task `A/B/C` variants inside each benchmark point.
- Expanded neural baselines:
  - existing numpy `MLP-explicit`, `MLP-latent`, `Elman`
  - new PyTorch `GRU`, `LSTM`, `causal Transformer`
- A collapse/frontier summary layer and SVG/Markdown report generation helpers.

## Key Design Choices

1. Benchmark points are task families, not single scenarios.
Each point carries task `A`, `B`, and `C` variants so cold-start aggregation and reduced transfer slices can use the same benchmark descriptor.

2. Hidden-memory and ambiguity families use explicit `target_bits`.
This keeps scoring deterministic and serializable while allowing harder task structures than the original named task registry alone supports.

3. Collapse is defined against both absolute REAL failure and relative NN separation.
REAL is only marked collapsed when it fails the fixed thresholds and a neural baseline clearly outperforms it, matching the paper goal of finding an obvious ceiling rather than a marginal dip.

4. Reporting stays dependency-light.
The first pass uses JSON manifests plus SVG/Markdown renderers instead of adding a plotting stack, so the benchmark remains easy to run in the standalone repo.

## Current Limits

- The pilot-tuning phase is represented in runner metadata and seed defaults, but no separate optimizer-sweep harness is implemented yet.
- The transfer slice is reduced and driven by the cold-start frontier, but it is not yet a separate publication-ready narrative on its own.
- PyTorch-backed smoke coverage depends on `torch` being installed in the local environment.
