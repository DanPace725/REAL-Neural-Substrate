# Phase 8 Session Summary — 2026-03-17

This document synthesizes the key findings from the 10 experimental traces generated today across the `REAL-Neural-Substrate` repository. The experiments primarily focused on testing latent context transfer robustness, large-topology morphogenesis, and sample-efficiency baselines.

---

## 1. Latent Transfer and Morphogenesis
Today's tests established clear differences in how *latent* vs *visible* context tracking affects transfer learning and network growth.

### Latent Context Transfer Robustness
Latent (inferred) context provides a massive advantage for transfer learning by avoiding "context poison."
* **Visible Training:** Builds strong context-specific action supports during Task A training. When transferring to Task B, the carried-over substrate forces incorrect transformations based on the previous context mappings.
* **Latent Training:** Infers context incrementally. Task A training often ends before firm context labels are assigned, leaving context-agnostic action supports. When arriving at Task B, the substrate doesn't force incorrect context mappings.
* **Transfer Result:** Latent `A -> B` transfer shows near-parity with visible transfer on exact matches (−0.4 exact, +0.011 bit accuracy) despite a much weaker cold-start performance on Task A. 

### Large-Topology Morphogenesis
Dynamic topology growth (morphogenesis) demonstrates varying utility depending on routing clarity and necessity.
* **Cold-Start Hard Task (Task B):** Visible morphogenesis provides the largest single gain (+7.4 exact matches, 80% win rate) because the low initial performance leaves ample ATP surplus and headroom to explore new routing options. 
* **Transfer (Warm Carryover):** Transfer + morphogenesis is the primary sweet spot. The warm substrate from Task A provides routing clarity, guiding the ATP surplus into generating highly productive +1.2 to +2.2 exact matches and an 80% win rate.
* **Self-Limiting Behavior:** Growth does not help when routing is already highly efficient (Tasks A and C). The disruption cost (~1.0–1.6 exact matches) outweighs the routing gains. ATP surplus naturally regulates this: efficient routing limits the surplus needed to trigger growth.

### Paired Visible vs Latent Morphogenesis
A paired evaluation on the large topology clarified the tradeoff:
* **Visible Growth:** Emphasized for cold-start maximums on the hardest scenarios.
* **Latent Growth:** Generates significantly stronger transfer improvements (+7.0 exact vs +2.2 exact for visible). It also reduces disruption costs on easier scenarios like Task A.

### Carryover Bridge Diagnostic
The poor performance of a naive "visible training -> latent transfer" mode-switch was found to be tied to episodic carryover. Testing with a `substrate-only` carryover mode (discarding episodic traces) rescued the transfer performance, proving that latent transfer requires specific substrate persistence state rather than full episodic baggage.

---

## 2. Cyclic Transfer Explorations
Initial cyclic transfer tests (`A -> B -> C -> A`) tested structural memory retention through multi-hop domains.

* **Visible Cyclic:** High variance and unstable. Average returns to Task A varied wildly by seed (+0.6 exact average), showing compound structural improvements but also heavy reintroduction of context poison.
* **Latent Cyclic:** More promising. Starting from a weaker cold `A` baseline, returning to `A` after the cycle yielded a solid +2.4 exact match average. Latent carryover proves far less vulnerable to long-chain context poisoning.

---

## 3. Sample-Efficiency Baselines
A formal evaluation using the new `neural_baseline.py` compared REAL against online SGD-trained MLP and RNN baselines using the 18-packet CVT-1 sequence constraints. 

* **The Sample Efficiency Ratio:** The Elman RNN baseline (most capable latent neural analogue) requires **8–9x more training examples (~150 examples / ~8-9 epochs)** to reach the ≥85% exact-match criterion that REAL achieves in a single 18-packet session.
* **Structural Failure:** The latent MLP cannot solve the bimodal mapping problem at all, failing to reach the criterion even after 20 epochs.
* **Scaled Architecture Match:** Scaling the neural architectures to 30 hidden units to match the 30-node REAL topology across a 108-packet stream yielded massive divergence: none of the MLPs/RNNs hit the criterion, topping out at ~16/108 exact matches. REAL achieved 100% criterion fulfillment on Task B and 60% on Tasks A/C, demonstrating that the allostatic substrate framework is fundamentally more memory-efficient during continuous execution than gradient weight adjustments.

---

## 4. Next Experimental Steps Identified
Based on today's synthesis, the most productive immediate follow-ups are:

1. **Latent Sequential Transfer Harness:** Expand `compare_sequential_transfer.py` to support latent context to firmly quantify the multi-chain latent carryover resilience.
2. **Context-Resolution Growth Gates:** Set `context_resolution_growth_gate: 0.55` in benchmark configs to prevent premature topology growth in environments lacking routing clarity (e.g., `branch_pressure`).
3. **Persisted Result Manifests:** Implement stable JSON result/trace capturing natively inside the harness runners for faster experimental iteration.
4. **Context-Agnostic Latent Training Action Supports:** Allow the latent pipeline to seed supports under a `context_bit=None` key to improve cold-start Task A learning speed without injecting transfer poison.
