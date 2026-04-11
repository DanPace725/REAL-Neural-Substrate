from __future__ import annotations

import unittest

from phase8 import bounded_ternary_overlap_topology, scenario_with_topology_mode
from phase8.hidden_regime import hidden_regime_suite_by_id
from scripts.compare_c_scale_suite import c_scale_suite_by_id
from scripts.evaluate_hidden_regime_forecasting import evaluate_hidden_regime_benchmark
from scripts.evaluate_laminated_phase8 import evaluate_laminated_benchmark


class TestCHRBoundedOverlapTopology(unittest.TestCase):
    def test_bounded_overlap_topology_has_expected_layer_widths_and_fanout(self) -> None:
        adjacency, positions, source_id, sink_id = bounded_ternary_overlap_topology()

        layers: dict[int, list[str]] = {}
        for node_id, position in positions.items():
            layers.setdefault(int(position), []).append(node_id)

        self.assertEqual(source_id, "n0")
        self.assertEqual(sink_id, "sink")
        self.assertEqual(len(layers[0]), 1)
        self.assertEqual(len(layers[1]), 3)
        self.assertEqual(len(layers[2]), 7)
        self.assertEqual(len(layers[3]), 15)
        self.assertEqual(len(layers[4]), 1)
        self.assertEqual(adjacency[source_id], tuple(sorted(layers[1], key=lambda item: int(item[1:]))))

        for node_id, neighbors in adjacency.items():
            if node_id == sink_id or node_id in layers[3]:
                continue
            self.assertLessEqual(len(neighbors), 3)
        for node_id in layers[3]:
            self.assertEqual(adjacency[node_id], (sink_id,))

    def test_scenario_override_replaces_topology_without_touching_schedule(self) -> None:
        base = c_scale_suite_by_id()["C3S1"].tasks["task_a"].visible_scenario
        overlap = scenario_with_topology_mode(base, "bounded_overlap_13715")

        self.assertNotEqual(base.positions, overlap.positions)
        self.assertEqual(base.initial_signal_specs, overlap.initial_signal_specs)
        self.assertEqual(base.signal_schedule_specs, overlap.signal_schedule_specs)
        self.assertEqual(len(overlap.positions), 27)
        self.assertEqual(max(overlap.positions.values()), 4)

    def test_c_laminated_eval_records_overlap_topology_mode(self) -> None:
        result = evaluate_laminated_benchmark(
            benchmark_id="C3S1",
            task_key="task_a",
            mode="visible",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=2,
            safety_limit=1,
            regulator_type="heuristic",
            topology_mode="bounded_overlap_13715",
            output_path=None,
        )

        self.assertEqual(result["topology_mode"], "bounded_overlap_13715")
        self.assertEqual(result["topology_node_count"], 27)
        self.assertEqual(result["topology_depth"], 4)

    def test_hidden_regime_eval_records_overlap_topology_mode(self) -> None:
        result = evaluate_hidden_regime_benchmark(
            benchmark_id="HR1",
            task_key="task_a",
            observable="hidden",
            seed=13,
            capability_policy="self-selected",
            initial_cycle_budget=2,
            safety_limit=1,
            regulator_type="heuristic",
            topology_mode="bounded_overlap_13715",
            output_path=None,
        )

        self.assertEqual(result["topology_mode"], "bounded_overlap_13715")
        self.assertEqual(result["topology_node_count"], 27)
        self.assertEqual(result["topology_depth"], 4)
        self.assertEqual(result["case"]["topology_name"], "bounded_overlap_13715")

    def test_hidden_regime_suite_legacy_topology_name_unchanged(self) -> None:
        suite = hidden_regime_suite_by_id()
        self.assertEqual(suite["HR1"].topology_name, "basic_demo")


if __name__ == "__main__":
    unittest.main()
