# Laminated REAL Substrate Report - Accuracy Analysis (Families A, B, and C)

This report provides a comprehensive summary of the recent lamination tests across task families A, B, and C, based on the outputs generated in the `docs/experiment_outputs` directory. This analysis focuses specifically on the **accuracy metrics** achieved by the REAL multi-agent substrate under varying topologies and routing conditions, including performance over multiple evaluation slices.

## 1. Overview

Lamination tests explore the capacity of the REAL multi-agent substrate to handle various routing topologies and capabilities over multiple stages. We analyzed outputs for three main families:
* **Family A**: Baseline topology scaling tests on Task A.
* **Family B**: Tests on scaling and various setups, expanding on capability routing combinations, covering Task A, Task B, and Task C.
* **Family C**: Tests targeting ambiguous routing scenarios with specific node architectures.

The primary metrics evaluated in this report are:
* **Delivery Ratio**: The percentage of successfully delivered packets. (Included for context on substrate stability).
* **Total Slices**: The number of sequential evaluation slices the simulation ran through before stabilizing or completing.
* **Mean Bit Accuracy**: The average accuracy of the feature bits delivered across all slices.
* **Final Slice Accuracy**: The mean bit accuracy recorded specifically during the *final* evaluation slice, showing the network's settled state.
* **Exact Match Ratio**: The ratio of perfectly matched delivered packets compared to total delivered packets across the entire run.

## 2. Experimental Results Summary

### Detailed Accuracy Table

| Family | Task | Scenario | Setup | Delivery Ratio | Total Slices | Mean Bit Acc | Final Slice Acc | Exact Match Ratio |
|---|---|---|---|---|---|---|---|---|
| A | Task A | a1 | Standard | 1.0000 | 12 | 0.6477 | 0.9375 | 0.4432 |
| A | Task A | a2 | Standard | 1.0000 | 6 | 0.7344 | 0.8125 | 0.6562 |
| A | Task A | a3 | Standard | 0.9844 | 9 | 0.7063 | 0.8571 | 0.5397 |
| A | Task A | a4 | Standard | 0.9940 | 22 | 0.6168 | 0.9375 | 0.3832 |
| B | Task A | b2s1 | Standard | 1.0000 | 7 | 0.6979 | 0.9375 | 0.4792 |
| B | Task A | b2s1 | visible_s10_b2 | 1.0000 | 10 | 0.4643 | 0.0000 | 0.1429 |
| B | Task A | b2s1 | visible_s10_b8 | 1.0000 | 2 | 0.5625 | 0.5625 | 0.2500 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 2 | 0.5625 | 0.5625 | 0.2500 |
| B | Task A | b2s1 | visible_s3_b8 | 1.0000 | 3 | 0.4722 | 0.0000 | 0.1667 |
| B | Task A | b2s1 | visible_s5_b4 | 1.0000 | 5 | 0.5357 | 0.5000 | 0.2143 |
| B | Task A | b2s2 | Standard | 1.0000 | 13 | 0.6761 | 0.8125 | 0.5114 |
| B | Task A | b2s2 | visible_s10_b4 | 1.0000 | 10 | 0.6607 | 1.0000 | 0.4286 |
| B | Task A | b2s2 | visible_s10_b8 | 1.0000 | 10 | 0.4286 | 0.0000 | 0.0714 |
| B | Task A | b2s2 | visible_s5_b8 | 1.0000 | 5 | 0.4464 | 0.6250 | 0.0714 |
| B | Task A | b2s2 | visible_s5_b9 | 1.0000 | 5 | 0.7593 | 1.0000 | 0.5926 |
| B | Task A | b2s3 | Standard | 1.0000 | 5 | 0.7031 | 0.8125 | 0.4688 |
| B | Task A | b2s3 | visible_s10_b12 | 1.0000 | 4 | 0.8056 | 0.9167 | 0.6389 |
| B | Task A | b2s3 | visible_s5_b25 | 1.0000 | 5 | 0.6491 | 0.6579 | 0.4035 |
| B | Task A | b2s4 | Standard | 1.0000 | 17 | 0.5583 | 1.0000 | 0.2667 |
| B | Task A | b2s4 | visible_s10_b24 | 0.9762 | 10 | 0.5325 | 0.3462 | 0.2114 |
| B | Task A | b2s4 | visible_s5_b48 | 1.0000 | 5 | 0.6054 | 0.9259 | 0.2857 |
| B | Task A | b2s5 | Standard | 0.9922 | 18 | 0.6575 | 0.8125 | 0.4567 |
| B | Task A | b2s5 | visible_s10_b47 | 0.9896 | 5 | 0.8158 | 0.9615 | 0.7053 |
| B | Task A | b2s5 | visible_s5_b95 | 1.0000 | 5 | 0.8635 | 0.8796 | 0.7745 |
| B | Task A | b2s6 | Standard | 0.9922 | 194 | 0.5532 | 0.8333 | 0.2461 |
| B | Task A | b2s6 | visible_s10_b90 | 0.9914 | 10 | 0.5152 | 0.5000 | 0.1323 |
| B | Task A | b2s6 | visible_s5_b180 | 1.0000 | 5 | 0.6173 | 0.4861 | 0.3488 |
| B | Task B | b2s1 | Standard | 1.0000 | 11 | 0.5938 | 0.9375 | 0.3500 |
| B | Task B | b2s2 | Standard | 1.0000 | 4 | 0.8333 | 0.8125 | 0.7083 |
| B | Task B | b2s3 | Standard | 1.0000 | 16 | 0.5759 | 0.9375 | 0.2946 |
| B | Task B | b2s4 | Standard | 0.9837 | 24 | 0.7044 | 0.8333 | 0.5083 |
| B | Task C | b2s1 | Standard | 1.0000 | 8 | 0.5312 | 0.9375 | 0.5208 |
| B | Task C | b2s2 | Standard | 0.9821 | 8 | 0.7273 | 0.8750 | 0.6364 |
| B | Task C | b2s3 | Standard | 1.0000 | 6 | 0.7625 | 1.0000 | 0.6000 |
| B | Task C | b2s4 | Standard | 1.0000 | 10 | 0.7266 | 1.0000 | 0.5625 |
| C | Task A | c3s1 | Standard | 0.9972 | 181 | 0.6417 | 0.8125 | 0.4109 |
| C | Task A | c3s2 | Standard | 0.9911 | 17 | 0.6622 | 0.9375 | 0.4505 |
| C | Task A | c3s3 | Standard | 0.9984 | 80 | 0.5843 | 0.8125 | 0.3371 |
| C | Task A | c3s4 | Standard | 0.9967 | 500 | 0.5232 | 0.5556 | 0.2058 |

## 3. Analysis by Family

### Family A
Family A acts as the baseline for scaling. Accuracy results demonstrate that as the scale increases (`a1` to `a4`), the substrate maintains a relatively stable overall `Mean Bit Accuracy` (0.61 - 0.73). Notably, the `Final Slice Accuracy` often finishes very strong (frequently peaking at 0.9375), showing that even if early slices struggle, the substrate can learn and stabilize to high accuracy by the end of the evaluation phase. However, `Exact Match Ratio` drops significantly in `a4` (0.38), indicating that achieving perfectly exact pattern matching becomes substantially more difficult as path complexity increases.

### Family B
Family B introduces significant variations in setups (e.g., `visible_s10_b2`, `visible_s5_b48`).
* **Setup Impact on Accuracy**: The `visible` setups demonstrate a wide variance in accuracy. For example, `b2s1` with standard setup reaches 0.69 `Mean Bit Accuracy` and finishes with a 0.9375 `Final Slice Accuracy`. Modifying it to `visible_s10_b2` drops mean accuracy sharply to 0.46, and it completely fails to resolve by the final slice (0.0000).
* **Large Scale Compensation**: In highly scaled scenarios like `b2s5`, specific visible setups actually *outperform* standard setups. `b2s5 visible_s5_b95` achieved an impressive 0.86 `Mean Bit Accuracy` and a 0.8796 `Final Slice Accuracy`, far exceeding the standard setup.
* **Slice Convergence**: In almost all standard setups across Task B, the `Final Slice Accuracy` settles into the 0.80 - 1.00 range, demonstrating excellent convergence capabilities regardless of the initial `Mean Bit Accuracy` drag from early slices.

### Family C
Family C targets complex, ambiguous routing scenarios (bridging architectures).
* The scenario requires drastically more slices to reach conclusion as ambiguity increases. `c3s1` requires 181 slices, and `c3s4` requires a massive 500 slices.
* Accuracy starts moderately strong in `c3s1` (0.64 `Mean Bit Accuracy`, 0.8125 `Final Slice Accuracy`) but exhibits a clear degradation pattern as the scenario scales up to `c3s4` (dropping to 0.52 `Mean Bit Accuracy` and settling at a mediocre 0.5556 `Final Slice Accuracy`).
* Despite the steady drop in feature accuracy and the sheer volume of slices required in more complex ambiguous routing setups, the substrate's `Delivery Ratio` remains incredibly high (> 0.99). This highlights a key behavioral trait of the current REAL configuration: it prioritizes packet delivery and flow maintenance over pattern precision under highly ambiguous constraints.

## 4. Conclusion
The lamination tests reveal that while the REAL multi-agent substrate is extremely robust in maintaining delivery across complex and growing topologies, **accuracy is highly sensitive to topological scale and capability routing setups**.
The substrate often maintains a base level of mean bit accuracy (around 50-60%), but perfecting the output requires carefully matched configurations (like `b2s5 visible_s5_b95`). More importantly, looking at the **Final Slice Accuracy** shows that the REAL substrate possesses a strong capacity to *converge* on highly accurate routing solutions (often > 0.85) by the end of its runs, provided the ambiguity doesn't overwhelm the network (as seen in the extreme Family C scenarios, which trade accuracy for delivery stability).
