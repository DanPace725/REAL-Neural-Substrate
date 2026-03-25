import unittest

from scripts.compare_c_scale_suite import build_c_scale_cases, c_scale_suite_by_id, evaluate_c_scale_suite


class TestCScaleSuite(unittest.TestCase):
    def test_c3_suite_shape(self) -> None:
        cases = build_c_scale_cases()

        self.assertEqual(
            tuple(case.benchmark_id for case in cases),
            ("C3S1", "C3S2", "C3S3", "C3S4", "C3S5", "C3S6"),
        )
        self.assertEqual([case.node_count for case in cases], [6, 10, 30, 50, 75, 100])
        self.assertEqual([case.expected_examples for case in cases], [18, 36, 108, 216, 432, 864])

    def test_generated_cases_have_visible_and_latent_tasks(self) -> None:
        suite = c_scale_suite_by_id()
        for benchmark_id in ("C3S5", "C3S6"):
            case = suite[benchmark_id]
            self.assertEqual(case.source, "generated_topology")
            self.assertEqual(tuple(case.tasks.keys()), ("task_a", "task_b", "task_c"))
            task_a = case.tasks["task_a"]
            self.assertIsNotNone(task_a.visible_scenario.initial_signal_specs[0].context_bit)
            self.assertIsNone(task_a.latent_scenario.initial_signal_specs[0].context_bit)
            self.assertEqual(
                len(task_a.visible_scenario.initial_signal_specs) + len(task_a.visible_scenario.signal_schedule_specs or {}),
                case.expected_examples,
            )

    def test_evaluate_c_scale_suite_smoke(self) -> None:
        result = evaluate_c_scale_suite(
            benchmark_ids=("C3S1",),
            task_keys=("task_a",),
            method_ids=("fixed-visible",),
            seeds=(13,),
        )

        self.assertEqual(result["benchmark_ids"], ["C3S1"])
        self.assertEqual(result["task_keys"], ["task_a"])
        self.assertEqual(result["method_ids"], ["fixed-visible"])
        self.assertEqual(result["seeds"], [13])
        self.assertEqual(len(result["runs"]), 1)
        self.assertEqual(len(result["aggregates"]), 1)
        run = result["runs"][0]
        aggregate = result["aggregates"][0]
        self.assertEqual(run["benchmark_id"], "C3S1")
        self.assertEqual(run["method_id"], "fixed-visible")
        self.assertGreater(run["elapsed_seconds"], 0.0)
        self.assertGreater(run["examples_per_second"], 0.0)
        self.assertIn("elapsed_ratio_vs_s1", aggregate)
        self.assertAlmostEqual(float(aggregate["elapsed_ratio_vs_s1"]), 1.0, places=4)
        self.assertIsNone(result["transfer_slice"])

    def test_evaluate_c_scale_suite_transfer_smoke(self) -> None:
        result = evaluate_c_scale_suite(
            benchmark_ids=("C3S1",),
            task_keys=("task_a",),
            method_ids=("fixed-visible",),
            seeds=(13,),
            include_transfer=True,
            train_task_key="task_a",
            transfer_task_keys=("task_c",),
        )

        transfer_slice = result["transfer_slice"]
        self.assertIsNotNone(transfer_slice)
        assert transfer_slice is not None
        self.assertEqual(transfer_slice["train_task_key"], "task_a")
        self.assertEqual(transfer_slice["transfer_task_keys"], ["task_c"])
        self.assertEqual(len(transfer_slice["runs"]), 2)
        self.assertEqual(
            {run["transfer_mode"] for run in transfer_slice["runs"]},
            {"cold", "warm"},
        )
        self.assertEqual(
            {run["transfer_task_key"] for run in transfer_slice["runs"]},
            {"task_c"},
        )
        warm_aggregate = next(
            aggregate
            for aggregate in transfer_slice["aggregates"]
            if aggregate["transfer_mode"] == "warm"
        )
        self.assertIn("exact_match_rate_delta_vs_cold", warm_aggregate)
        self.assertIn("bit_accuracy_delta_vs_cold", warm_aggregate)
        self.assertIn("elapsed_ratio_vs_cold", warm_aggregate)
        self.assertEqual(warm_aggregate["task_key"], "task_a")
        self.assertEqual(warm_aggregate["transfer_task_key"], "task_c")


if __name__ == "__main__":
    unittest.main()
