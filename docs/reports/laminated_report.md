# Laminated REAL Substrate Report - Accuracy Analysis (Families A, B, and C)

This report provides a comprehensive summary of the recent lamination tests across task families A, B, and C, based on the outputs generated in the `docs/experiment_outputs` directory. This analysis focuses specifically on the **accuracy metrics** achieved by the REAL multi-agent substrate under varying topologies and routing conditions.

## 1. Overview

Lamination tests explore the capacity of the REAL multi-agent substrate to handle various routing topologies and capabilities over multiple stages. We analyzed outputs for three main families:
* **Family A**: Baseline topology scaling tests on Task A.
* **Family B**: Tests on scaling and various setups, expanding on capability routing combinations, covering Task A, Task B, and Task C.
* **Family C**: Tests targeting ambiguous routing scenarios with specific node architectures.

The primary metrics evaluated in this report are:
* **Delivery Ratio**: The percentage of successfully delivered packets. (Included for context on substrate stability).
* **Mean Bit Accuracy**: The average accuracy of the feature bits delivered across the network.
* **Exact Match Ratio**: The ratio of perfectly matched delivered packets compared to total delivered packets.

## 2. Experimental Results Summary

### Detailed Accuracy Table

| Family | Task | Scenario | Setup | Delivery Ratio | Mean Bit Accuracy | Exact Match Ratio |
|---|---|---|---|---|---|---|
| A | Task A | a1 | Standard | 1.0000 | 0.6477 | 0.4432 |
| A | Task A | a2 | Standard | 1.0000 | 0.7344 | 0.6562 |
| A | Task A | a3 | Standard | 0.9844 | 0.7063 | 0.5397 |
| A | Task A | a4 | Standard | 0.9940 | 0.6168 | 0.3832 |
| B | Task A | b2s1 | Standard | 1.0000 | 0.6979 | 0.4792 |
| B | Task A | b2s1 | visible_s10_b2 | 1.0000 | 0.4643 | 0.1429 |
| B | Task A | b2s1 | visible_s10_b8 | 1.0000 | 0.5625 | 0.2500 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 0.5625 | 0.2500 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 0.4722 | 0.1667 |
| B | Task A | b2s1 | visible_s5_b4 | 1.0000 | 0.5357 | 0.2143 |
| B | Task A | b2s2 | Standard | 1.0000 | 0.6761 | 0.5114 |
| B | Task A | b2s2 | visible_s10_b4 | 1.0000 | 0.6607 | 0.4286 |
| B | Task A | b2s2 | visible_s10_b8 | 1.0000 | 0.4286 | 0.0714 |
| B | Task A | b2s2 | visible_s5_b8 | 1.0000 | 0.4464 | 0.0714 |
| B | Task A | b2s2 | visible_s5_b9 | 1.0000 | 0.7593 | 0.5926 |
| B | Task A | b2s3 | Standard | 1.0000 | 0.7031 | 0.4688 |
| B | Task A | b2s3 | visible_s10_b12 | 1.0000 | 0.8056 | 0.6389 |
| B | Task A | b2s3 | visible_s5_b25 | 1.0000 | 0.6491 | 0.4035 |
| B | Task A | b2s4 | Standard | 1.0000 | 0.5583 | 0.2667 |
| B | Task A | b2s4 | visible_s10_b24 | 0.9762 | 0.5325 | 0.2114 |
| B | Task A | b2s4 | visible_s5_b48 | 1.0000 | 0.6054 | 0.2857 |
| B | Task A | b2s5 | Standard | 0.9922 | 0.6575 | 0.4567 |
| B | Task A | b2s5 | visible_s10_b47 | 0.9896 | 0.8158 | 0.7053 |
| B | Task A | b2s5 | visible_s5_b95 | 1.0000 | 0.8635 | 0.7745 |
| B | Task A | b2s6 | Standard | 0.9922 | 0.5532 | 0.2461 |
| B | Task A | b2s6 | visible_s10_b90 | 0.9914 | 0.5152 | 0.1323 |
| B | Task A | b2s6 | visible_s5_b180 | 1.0000 | 0.6173 | 0.3488 |
| B | Task B | b2s1 | Standard | 1.0000 | 0.5938 | 0.3500 |
| B | Task B | b2s2 | Standard | 1.0000 | 0.8333 | 0.7083 |
| B | Task B | b2s3 | Standard | 1.0000 | 0.5759 | 0.2946 |
| B | Task B | b2s4 | Standard | 0.9837 | 0.7044 | 0.5083 |
| B | Task C | b2s1 | Standard | 1.0000 | 0.5312 | 0.5208 |
| B | Task C | b2s2 | Standard | 0.9821 | 0.7273 | 0.6364 |
| B | Task C | b2s3 | Standard | 1.0000 | 0.7625 | 0.6000 |
| B | Task C | b2s4 | Standard | 1.0000 | 0.7266 | 0.5625 |
| C | Task A | c3s1 | Standard | 0.9972 | 0.6417 | 0.4109 |
| C | Task A | c3s2 | Standard | 0.9911 | 0.6622 | 0.4505 |
| C | Task A | c3s3 | Standard | 0.9984 | 0.5843 | 0.3371 |
| C | Task A | c3s4 | Standard | 0.9967 | 0.5232 | 0.2058 |

## 3. Analysis by Family

### Family A
Family A acts as the baseline for scaling. Accuracy results demonstrate that as the scale increases (`a1` to `a4`), the substrate maintains a relatively stable `Mean Bit Accuracy` (0.61 - 0.73). Notably, the `Exact Match Ratio` peaks at `a2` (0.65) but drops significantly in `a4` (0.38), indicating that while bits are generally correct, achieving perfectly exact pattern matching becomes substantially more difficult as path complexity and node count increase, even while keeping delivery ratios near perfect.

### Family B
Family B introduces significant variations in setups (e.g., `visible_s10_b2`, `visible_s5_b48`).
* **Setup Impact on Accuracy**: The `visible` setups demonstrate a wide variance in accuracy. For example, `b2s1` with standard setup reaches 0.69 `Mean Bit Accuracy`, but modifying it to `visible_s10_b2` drops it sharply to 0.46, with `Exact Match Ratio` dropping from 0.47 to 0.14.
* **Large Scale Compensation**: Interestingly, in highly scaled scenarios like `b2s5`, specific visible setups actually *outperform* standard setups in accuracy. `b2s5 visible_s5_b95` achieved an impressive 0.86 `Mean Bit Accuracy` and 0.77 `Exact Match Ratio`, far exceeding the standard setup (0.65 and 0.45, respectively).
* **Task Variability**: Accuracy fluctuates notably when testing Task B and Task C compared to Task A, indicating that routing and classification accuracy are strongly dependent on the inherent structure of the task, not just the topology scale.

### Family C
Family C targets complex, ambiguous routing scenarios (bridging architectures).
* Accuracy starts moderately strong in `c3s1` (0.64 `Mean Bit Accuracy`, 0.41 `Exact Match Ratio`) but exhibits a clear degradation pattern as the scenario scales up to `c3s4` (dropping to 0.52 `Mean Bit Accuracy` and just 0.20 `Exact Match Ratio`).
* Despite the steady drop in feature accuracy in more complex ambiguous routing setups, the substrate's `Delivery Ratio` remains incredibly high (> 0.99). This highlights a key behavioral trait of the current REAL configuration: it prioritizes packet delivery and flow maintenance over pattern precision under highly ambiguous constraints.

## 4. Conclusion
The lamination tests reveal that while the REAL multi-agent substrate is extremely robust in maintaining delivery across complex and growing topologies, **accuracy (especially Exact Match Ratio) is highly sensitive to topological scale and capability routing setups**.
The substrate often maintains a base level of mean bit accuracy (around 50-60%), but perfecting the output requires carefully matched configurations (like `b2s5 visible_s5_b95`). Furthermore, in highly ambiguous routing environments (Family C), the network trades accuracy for delivery stability, heavily degrading exact matches as complexity peaks.
