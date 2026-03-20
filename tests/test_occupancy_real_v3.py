from __future__ import annotations

import unittest
from unittest.mock import patch

from occupancy_baseline import get_preset
from occupancy_baseline.session_splitter import assign_context_codes, compute_training_medians, segment_into_sessions
from scripts.occupancy_real_v3 import (
    CONTEXT_LATENT,
    CONTEXT_ONLINE,
    EVAL_FRESH,
    OccupancyRealV3Config,
    TOPOLOGY_FIXED,
    TOPOLOGY_MULTIHOP,
    _context_code_from_means,
    _context_codes_for_session,
    _context_transfer_probe,
    _mean_feature_for_episode,
    load_all_episodes_v3,
    resolve_sweep_worker_plan,
    run_occupancy_real_v3_experiment,
    run_occupancy_real_v3_sweep,
)


def _mini_v3_config(**overrides) -> OccupancyRealV3Config:
    preset = get_preset("synth_v1_default")
    cfg = preset.config
    summary_only = bool(overrides.pop("summary_only", False))
    selector_seed = int(overrides.pop("selector_seed", 13))
    max_train_sessions = int(overrides.pop("max_train_sessions", 2))
    max_eval_sessions = int(overrides.pop("max_eval_sessions", 2))
    return OccupancyRealV3Config(
        csv_path=cfg.csv_path,
        window_size=cfg.window_size,
        normalize=cfg.normalize,
        selector_seed=selector_seed,
        max_train_sessions=max_train_sessions,
        max_eval_sessions=max_eval_sessions,
        summary_only=summary_only,
        **overrides,
    )


class TestOccupancyRealV3(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.default_result = run_occupancy_real_v3_experiment(_mini_v3_config(), workers=1)
        cls.latent_result = run_occupancy_real_v3_experiment(
            _mini_v3_config(context_mode=CONTEXT_LATENT),
            workers=1,
        )

    def test_fresh_session_eval_resets_warm_and_cold_systems(self) -> None:
        result = self.default_result
        primary = result["primary_eval"]
        self.assertEqual(result["primary_eval_mode"], EVAL_FRESH)
        self.assertEqual(primary["warm_reset_count"], result["eval_session_count"])
        self.assertEqual(primary["cold_reset_count"], result["eval_session_count"])
        self.assertEqual(len(primary["warm_system_summaries"]), result["eval_session_count"])
        self.assertEqual(len(primary["cold_system_summaries"]), result["eval_session_count"])

    def test_default_ingress_uses_source_admission(self) -> None:
        result = self.default_result
        self.assertEqual(result["v3_config"]["ingress_mode"], "admission_source")
        self.assertGreater(result["train_system_summary"]["admitted_packets"], 0)
        self.assertGreater(result["warm_system_summary"]["admitted_packets"], 0)
        self.assertGreater(result["cold_system_summary"]["admitted_packets"], 0)

    def test_online_context_uses_only_seen_episodes(self) -> None:
        config = _mini_v3_config(summary_only=True)
        episodes = load_all_episodes_v3(config)
        sessions = segment_into_sessions(episodes)
        train_sessions = sessions[: max(1, round(len(sessions) * config.train_session_fraction))]
        co2_median, light_median = compute_training_medians(train_sessions)
        assigned = assign_context_codes(train_sessions, co2_median, light_median)
        session = next(session for session in assigned if len(session.episodes) > 1)

        online_codes = _context_codes_for_session(
            session,
            context_mode=CONTEXT_ONLINE,
            co2_median=co2_median,
            light_median=light_median,
        )
        first_episode = session.episodes[0]
        expected_first = _context_code_from_means(
            _mean_feature_for_episode(first_episode, "co2"),
            _mean_feature_for_episode(first_episode, "light"),
            co2_median,
            light_median,
        )

        self.assertEqual(online_codes[0], expected_first)
        self.assertEqual(online_codes[-1], session.context_code)

    def test_latent_context_mode_uses_no_explicit_context_codes(self) -> None:
        result = self.latent_result
        self.assertEqual(result["training_context_codes"], [])
        self.assertEqual(result["context_transfer_probe"]["status"], "not_applicable_latent_context")
        for session in result["train_session_results"]:
            self.assertTrue(all(code is None for code in session["episode_context_codes"]))

    def test_both_topologies_execute(self) -> None:
        for topology_mode in (TOPOLOGY_FIXED, TOPOLOGY_MULTIHOP):
            with self.subTest(topology_mode=topology_mode):
                result = run_occupancy_real_v3_experiment(
                    _mini_v3_config(topology_mode=topology_mode, summary_only=True),
                    workers=1,
                )
                self.assertIn("accuracy", result["warm_eval_summary"]["metrics"])
                self.assertEqual(result["v3_config"]["topology_mode"], topology_mode)

    def test_seen_only_context_probe_marked_not_applicable(self) -> None:
        probe = _context_transfer_probe(
            warm_results=[{"context_code": 0, "delivery_ratio": 0.8}],
            cold_results=[{"context_code": 0, "delivery_ratio": 0.7}],
            training_context_codes={0, 1},
            context_mode=CONTEXT_ONLINE,
        )
        self.assertFalse(probe["comparison_applicable"])
        self.assertEqual(probe["status"], "not_applicable_all_eval_contexts_seen")

    def test_sweep_worker_plan_targets_75_percent_cpu_budget(self) -> None:
        with patch("scripts.occupancy_real_v3.os.cpu_count", return_value=20):
            plan = resolve_sweep_worker_plan(selector_seed_count=3, workers=None)
        self.assertEqual(plan.worker_budget, 15)
        self.assertEqual(plan.seed_workers, 3)
        self.assertEqual(plan.eval_workers_per_seed, 5)
        self.assertEqual(plan.effective_total_workers, 15)

    def test_multi_seed_sweep_aggregates_seed_runs(self) -> None:
        result = run_occupancy_real_v3_sweep(
            _mini_v3_config(max_train_sessions=1, max_eval_sessions=1, summary_only=True),
            selector_seeds=(13, 23),
            workers=1,
        )
        self.assertEqual(result["aggregate"]["selector_seed_count"], 2)
        self.assertEqual(result["worker_policy"]["seed_workers"], 1)
        self.assertEqual(result["worker_policy"]["eval_workers_per_seed"], 1)
        self.assertEqual(
            [summary["selector_seed"] for summary in result["seed_summaries"]],
            [13, 23],
        )
        self.assertEqual(len(result["seed_results"]), 2)


if __name__ == "__main__":
    unittest.main()
