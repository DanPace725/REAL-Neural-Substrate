# Laminated REAL Substrate Report - Families A, B, and C

This report provides a comprehensive summary of the recent lamination tests across task families A, B, and C, based on the outputs generated in the `docs/experiment_outputs` directory.

## 1. Overview

Lamination tests explore the capacity of the REAL multi-agent substrate to handle various routing topologies and capabilities over multiple stages. We analyzed outputs for three main families:
* **Family A**: Baseline topology scaling tests on Task A.
* **Family B**: Tests on scaling and various setups, expanding on capability routing combinations, covering Task A, Task B, and Task C.
* **Family C**: Tests targeting ambiguous routing scenarios with specific node architectures.

## 2. Experimental Results Summary

The table below details the performance of each lamination scenario. Key metrics include:
* **Delivery Ratio**: The percentage of successfully delivered packets.
* **Drop Ratio**: The percentage of dropped packets.
* **Latency**: The mean packet latency across the topology.
* **Hops**: The mean number of hops taken to deliver a packet.
* **Total ATP**: A measure of the energetic cost for the nodes within the substrate.

### Detailed Table

| Family | Task | Scenario | Setup | Delivery Ratio | Drop Ratio | Latency | Hops | Total ATP |
|---|---|---|---|---|---|---|---|---|
| A | Task A | a1 | Standard | 1.0000 | 0.0000 | 1.00 | 3.00 | 3.41 |
| A | Task A | a2 | Standard | 1.0000 | 0.0000 | 1.00 | 5.00 | 8.42 |
| A | Task A | a3 | Standard | 0.9844 | 0.0000 | 1.14 | 6.79 | 12.63 |
| A | Task A | a4 | Standard | 0.9940 | 0.0000 | 1.77 | 7.57 | 17.83 |
| B | Task A | b2s1 | Standard | 1.0000 | 0.0000 | 1.00 | 3.00 | 3.44 |
| B | Task A | b2s1 | visible_s10_b2 | 1.0000 | 0.0000 | 1.00 | 3.00 | 5.03 |
| B | Task A | b2s1 | visible_s10_b8 | 1.0000 | 0.0000 | 1.00 | 3.00 | 5.78 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 0.0000 | 1.00 | 3.00 | 5.78 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 0.0000 | 1.00 | 3.00 | 4.31 |
| B | Task A | b2s1 | visible_s5_b4 | 1.0000 | 0.0000 | 1.00 | 3.00 | 5.57 |
| B | Task A | b2s2 | Standard | 1.0000 | 0.0000 | 1.00 | 5.00 | 7.13 |
| B | Task A | b2s2 | visible_s10_b4 | 1.0000 | 0.0000 | 1.00 | 5.00 | 7.06 |
| B | Task A | b2s2 | visible_s10_b8 | 1.0000 | 0.0000 | 1.00 | 5.00 | 6.32 |
| B | Task A | b2s2 | visible_s5_b8 | 1.0000 | 0.0000 | 1.00 | 5.00 | 8.52 |
| B | Task A | b2s2 | visible_s5_b9 | 1.0000 | 0.0000 | 1.26 | 5.00 | 7.98 |
| B | Task A | b2s3 | Standard | 1.0000 | 0.0000 | 1.00 | 6.25 | 14.03 |
| B | Task A | b2s3 | visible_s10_b12 | 1.0000 | 0.0000 | 1.00 | 6.50 | 14.17 |
| B | Task A | b2s3 | visible_s5_b25 | 1.0000 | 0.0000 | 1.23 | 6.37 | 11.38 |
| B | Task A | b2s4 | Standard | 1.0000 | 0.0000 | 2.62 | 7.47 | 13.02 |
| B | Task A | b2s4 | visible_s10_b24 | 0.9762 | 0.0000 | 2.48 | 7.84 | 12.49 |
| B | Task A | b2s4 | visible_s5_b48 | 1.0000 | 0.0000 | 2.01 | 7.58 | 13.91 |
| B | Task A | b2s5 | Standard | 0.9922 | 0.0000 | 2.62 | 11.00 | 23.53 |
| B | Task A | b2s5 | visible_s10_b47 | 0.9896 | 0.0000 | 1.75 | 11.00 | 23.15 |
| B | Task A | b2s5 | visible_s5_b95 | 1.0000 | 0.0000 | 1.27 | 11.00 | 9.92 |
| B | Task A | b2s6 | Standard | 0.9922 | 0.0065 | 4.04 | 10.00 | 26.49 |
| B | Task A | b2s6 | visible_s10_b90 | 0.9914 | 0.0043 | 3.38 | 10.00 | 21.66 |
| B | Task A | b2s6 | visible_s5_b180 | 1.0000 | 0.0000 | 4.67 | 10.00 | 11.86 |
| B | Task B | b2s1 | Standard | 1.0000 | 0.0000 | 1.00 | 3.00 | 4.61 |
| B | Task B | b2s2 | Standard | 1.0000 | 0.0000 | 1.00 | 5.00 | 8.92 |
| B | Task B | b2s3 | Standard | 1.0000 | 0.0000 | 1.46 | 6.79 | 15.63 |
| B | Task B | b2s4 | Standard | 0.9837 | 0.0163 | 1.69 | 7.30 | 14.05 |
| B | Task C | b2s1 | Standard | 1.0000 | 0.0000 | 1.00 | 3.00 | 4.68 |
| B | Task C | b2s2 | Standard | 0.9821 | 0.0000 | 1.18 | 5.00 | 7.48 |
| B | Task C | b2s3 | Standard | 1.0000 | 0.0000 | 1.00 | 6.75 | 11.03 |
| B | Task C | b2s4 | Standard | 1.0000 | 0.0000 | 1.36 | 7.27 | 13.55 |
| C | Task A | c3s1 | Standard | 0.9972 | 0.0021 | 2.07 | 3.00 | 3.57 |
| C | Task A | c3s2 | Standard | 0.9911 | 0.0000 | 1.57 | 5.00 | 8.23 |
| C | Task A | c3s3 | Standard | 0.9984 | 0.0000 | 1.64 | 6.85 | 11.25 |
| C | Task A | c3s4 | Standard | 0.9967 | 0.0028 | 3.18 | 7.69 | 17.76 |

## 3. Analysis by Family

### Family A
Family A acts as a baseline, showing near-perfect delivery ratios (0.98 - 1.0) with scaling scenarios (`a1` to `a4`). As the scenario scales, both the number of hops and the total ATP scale smoothly, maintaining zero dropped packets.

### Family B
Family B is tested extensively, exploring variations in `visible` parameters alongside standard scenarios across tasks A, B, and C.
* **Delivery rates** are mostly pristine, usually exactly 1.0 or very close. In large topologies like `b2s6`, we see some minor drop ratios (< 0.01) with certain setups.
* **Task Variability**: It successfully scales across tasks A, B, and C, maintaining high delivery.
* **Setups**: The visible configurations (e.g., `visible_s10_b90`, `visible_s5_b180`) generally manage equivalent delivery and latency to standard ones. Interestingly, specific visible setups sometimes exhibit lower total ATP despite high complexity (e.g., `b2s6 visible_s5_b180` at 11.86 ATP compared to `Standard` at 26.49 ATP).

### Family C
Family C targets complex multi-agent bridging setups.
* It maintains highly competitive performance on Task A across `c3s1` to `c3s4`, with delivery ratios consistently > 0.99.
* Drop ratios appear slightly higher than early Family A & B tests but stay below 0.003, showing the REAL substrate successfully navigates complex topological ambiguities.

## 4. Conclusion
Across all three families and task configurations, the REAL multi-agent substrate shows robust routing and delivery capabilities. Even as latency and hop counts increase with topological scale, the delivery ratio remains exceptional (> 97% across all extreme scenarios and > 99% in almost all tests), confirming stability and energetic efficiency (ATP usage scales logically and can be optimized through explicit setups).
