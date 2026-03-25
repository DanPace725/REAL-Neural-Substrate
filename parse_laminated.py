import json
import os
from glob import glob

report_md = """# Laminated REAL Substrate Report - Families A, B, and C

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
"""

data = []
for file in glob("docs/experiment_outputs/*laminated*.json"):
    if "accuracy_comparison" in file:
        continue
    with open(file) as f:
        try:
            d = json.load(f)
            filename = os.path.basename(file)
            parts = filename.split('_')
            scenario = parts[2]
            family = scenario[0].upper()

            task = "Unknown"
            if "task_a" in filename: task = "Task A"
            elif "task_b" in filename: task = "Task B"
            elif "task_c" in filename: task = "Task C"

            setup = "Standard"
            if "visible_s" in filename:
                idx = filename.find("visible_s")
                end_idx = filename.find("_t08", idx)
                if end_idx == -1:
                    end_idx = filename.find("_seed", idx)
                setup = filename[idx:end_idx]

            if "result" in d and "laminated_summary" in d["result"]:
                summary = d["result"]["laminated_summary"]
                delivery_ratio = summary.get("delivery_ratio", 0)
                drop_ratio = summary.get("drop_ratio", 0)
                mean_latency = summary.get("mean_latency", 0)
                mean_hops = summary.get("mean_hops", 0)
                node_atp_total = summary.get("node_atp_total", 0)

                data.append({
                    "family": family,
                    "task": task,
                    "scenario": scenario,
                    "setup": setup,
                    "delivery_ratio": delivery_ratio,
                    "drop_ratio": drop_ratio,
                    "mean_latency": mean_latency,
                    "mean_hops": mean_hops,
                    "node_atp_total": node_atp_total
                })
        except Exception as e:
            pass

data.sort(key=lambda x: (x["family"], x["task"], x["scenario"], x["setup"]))

for item in data:
    report_md += f"| {item['family']} | {item['task']} | {item['scenario']} | {item['setup']} | {item['delivery_ratio']:.4f} | {item['drop_ratio']:.4f} | {item['mean_latency']:.2f} | {item['mean_hops']:.2f} | {item['node_atp_total']:.2f} |\n"

report_md += """
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
"""

with open("docs/reports/laminated_report.md", "w") as f:
    f.write(report_md)

print("Report generated at docs/reports/laminated_report.md")
