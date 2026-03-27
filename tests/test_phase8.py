from __future__ import annotations

import json
import unittest
import uuid
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from phase8 import (
    ConnectionSubstrate,
    MorphogenesisConfig,
    NativeSubstrateSystem,
    RoutingEnvironment,
    SignalPacket,
    SignalSpec,
    phase8_scenarios,
)
from scripts.compare_morphogenesis import (
    aggregate_growth_results,
    compare_growth_for_seed,
    evaluate_morphogenesis,
    growth_counts_as_earned,
    growth_counts_as_win,
)
from scripts.compare_cyclic_transfer import evaluate_cyclic_transfer
from scripts.compare_large_topology import evaluate_large_topology
from compare_morphogenesis_large_carryover_bridge import evaluate_morphogenesis_large_carryover_bridge
from scripts.compare_morphogenesis_large import evaluate_morphogenesis_large
from scripts.compare_morphogenesis_large_paired import evaluate_morphogenesis_large_paired
from compare_morphogenesis_large_mode_switched import evaluate_morphogenesis_large_mode_switched
from scripts.compare_sequential_transfer import evaluate_sequential_transfer
from scripts.analyze_transfer_timecourse import _aggregate_latent_variant, _latent_timeline_summary
from scripts.compare_latent_context import latent_signal_specs
from scripts.neural_baseline import (
    BaselineResult,
    aggregate_results as aggregate_neural_results,
    examples_to_criterion,
)
from scripts.compare_task_transfer import aggregate_transfer, transfer_metrics
from phase8.consolidation import Phase8ConsolidationPipeline
from real_core.types import CycleEntry, GCOStatus


class TestSignalPacket(unittest.TestCase):
    def test_payload_defaults_to_input_bits(self) -> None:
        packet = SignalPacket(
            packet_id="pkt-test",
            origin="n0",
            target="sink",
            created_cycle=0,
            input_bits=[1, 0, 1, 2],
            context_bit=3,
        )

        self.assertEqual(packet.input_bits, [1, 0, 1, 1])
        self.assertEqual(packet.payload_bits, [1, 0, 1, 1])
        self.assertEqual(packet.context_bit, 3)


class TestConnectionSubstrate(unittest.TestCase):
    def test_investment_reduces_route_cost(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        baseline = substrate.use_cost("n1")
        first = substrate.invest_connection("n1", atp_budget=1.0)
        second = substrate.invest_connection("n1", atp_budget=1.0)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertLess(substrate.use_cost("n1"), baseline)

    def test_maintenance_refreshes_context_action_support(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=0.4,
            context_bit=0,
        )

        for _ in range(3):
            substrate.tick()

        self.assertGreater(substrate.action_support_age("n1", "rotate_left_1", 0), 0)

        result = substrate.maintain_supports(
            1.0,
            transform_credit={"rotate_left_1": 1.0},
            context_bit=0,
        )

        self.assertGreater(result["spent"], 0.0)
        self.assertIn("n1:rotate_left_1:context_0", result["maintained_actions"])
        self.assertEqual(substrate.action_support_age("n1", "rotate_left_1", 0), 0)

    def test_repeated_context_feedback_promotes_context_action_support(self) -> None:
        substrate = ConnectionSubstrate(("n1",))

        promoted = False
        for _ in range(4):
            promoted = substrate.record_context_feedback(
                "n1",
                "rotate_left_1",
                0,
                credit_signal=1.0,
                bit_match_ratio=1.0,
            ) or promoted

        self.assertTrue(promoted)
        self.assertGreaterEqual(
            substrate.contextual_action_support("n1", "rotate_left_1", 0),
            0.24,
        )
        self.assertEqual(
            substrate.contextual_action_support("n1", "rotate_left_1", 1),
            0.0,
        )

    def test_aligned_partial_context_feedback_preserves_support_and_accumulator(self) -> None:
        substrate = ConnectionSubstrate(("n1",))

        for _ in range(2):
            substrate.record_context_feedback(
                "n1",
                "identity",
                3,
                credit_signal=1.0,
                bit_match_ratio=1.0,
            )

        before_support = substrate.contextual_action_support("n1", "identity", 3)
        before_accumulator = substrate._context_credit_accumulator[
            substrate._credit_key("n1", "identity", 3)
        ]

        promoted = substrate.record_context_feedback(
            "n1",
            "identity",
            3,
            credit_signal=1.0,
            bit_match_ratio=0.5,
            aligned_transform=True,
        )

        after_support = substrate.contextual_action_support("n1", "identity", 3)
        after_accumulator = substrate._context_credit_accumulator[
            substrate._credit_key("n1", "identity", 3)
        ]

        self.assertFalse(promoted)
        self.assertGreater(before_support, 0.0)
        self.assertGreater(after_support, 0.0)
        self.assertGreater(after_support, before_support * 0.6)
        self.assertGreater(after_accumulator, before_accumulator * 0.5)

    def test_nonbinary_context_labels_can_be_registered_and_maintained(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=0.4,
            context_bit=3,
        )

        self.assertIn(3, substrate.supported_contexts)
        self.assertGreaterEqual(
            substrate.contextual_action_support("n1", "rotate_left_1", 3),
            0.4,
        )
        self.assertIn(
            ("n1", "rotate_left_1", 3),
            substrate.active_action_supports(),
        )

    def test_maintenance_avoids_high_debt_context_support_when_budget_is_tight(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "xor_mask_1010",
            value=0.45,
            context_bit=1,
        )
        substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )

        result = substrate.maintain_supports(
            0.04,
            transform_credit={"xor_mask_1010": 0.5, "xor_mask_0101": 0.5},
            context_transform_credit={
                "xor_mask_1010:context_1": 0.5,
                "xor_mask_0101:context_1": 0.5,
            },
            transform_debt={"xor_mask_1010": 0.8},
            context_transform_debt={"xor_mask_1010:context_1": 1.0},
            context_bit=1,
        )

        self.assertIn("n1:xor_mask_0101:context_1", result["maintained_actions"])
        self.assertNotIn("n1:xor_mask_1010:context_1", result["maintained_actions"])

    def test_maintenance_avoids_high_branch_context_debt_when_budget_is_tight(self) -> None:
        substrate = ConnectionSubstrate(("n1", "n2"))
        substrate.seed_support(("n1", "n2"), value=0.45)
        substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        substrate.seed_action_support(
            "n2",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )

        result = substrate.maintain_supports(
            0.03,
            transform_credit={"xor_mask_0101": 0.5},
            context_transform_credit={"xor_mask_0101:context_1": 0.5},
            branch_context_debt={"n1:context_1": 1.0},
            context_bit=1,
        )

        self.assertNotIn("n1:xor_mask_0101:context_1", result["maintained_actions"])
        self.assertIn("n2:xor_mask_0101:context_1", result["maintained_actions"])

    def test_maintenance_prefers_high_branch_context_credit_when_budget_is_tight(self) -> None:
        substrate = ConnectionSubstrate(("n1", "n2"))
        substrate.seed_support(("n1", "n2"), value=0.45)
        substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        substrate.seed_action_support(
            "n2",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )

        result = substrate.maintain_supports(
            0.03,
            transform_credit={"xor_mask_0101": 0.5},
            context_transform_credit={"xor_mask_0101:context_1": 0.5},
            branch_context_credit={"n2:context_1": 1.0},
            context_bit=1,
        )

        self.assertNotIn("n1:xor_mask_0101:context_1", result["maintained_actions"])
        self.assertIn("n2:xor_mask_0101:context_1", result["maintained_actions"])

    def test_maintenance_prefers_high_context_branch_transform_credit_when_budget_is_tight(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "xor_mask_1010",
            value=0.45,
            context_bit=1,
        )
        substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )

        result = substrate.maintain_supports(
            0.03,
            transform_credit={"xor_mask_1010": 0.5, "xor_mask_0101": 0.5},
            context_transform_credit={
                "xor_mask_1010:context_1": 0.5,
                "xor_mask_0101:context_1": 0.5,
            },
            branch_transform_credit={
                "n1:xor_mask_1010": 0.5,
                "n1:xor_mask_0101": 0.5,
            },
            context_branch_transform_credit={"n1:xor_mask_0101:context_1": 1.0},
            context_bit=1,
        )

        self.assertIn("n1:xor_mask_0101:context_1", result["maintained_actions"])
        self.assertNotIn("n1:xor_mask_1010:context_1", result["maintained_actions"])

    def test_low_match_context_feedback_demotes_context_action_support(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=0.6,
            context_bit=1,
        )

        before = substrate.contextual_action_support("n1", "rotate_left_1", 1)
        promoted = substrate.record_context_feedback(
            "n1",
            "rotate_left_1",
            1,
            credit_signal=0.5,
            bit_match_ratio=0.5,
        )

        self.assertFalse(promoted)
        self.assertLess(
            substrate.contextual_action_support("n1", "rotate_left_1", 1),
            before,
        )


class TestRoutingEnvironment(unittest.TestCase):
    def test_feedback_propagates_upstream_one_hop_per_tick(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(count=1)
        env.route_signal("n0", "n1", cost=0.05)
        env.route_signal("n1", "sink", cost=0.05)

        before_n0 = env.state_for("n0").atp
        before_n1 = env.state_for("n1").atp

        first_step = env.advance_feedback()
        self.assertEqual(len(first_step), 1)
        self.assertGreater(env.state_for("n1").atp, before_n1)
        self.assertAlmostEqual(env.state_for("n0").atp, before_n0, places=6)

        second_step = env.advance_feedback()
        self.assertEqual(len(second_step), 1)
        self.assertGreater(env.state_for("n0").atp, before_n0)

    def test_packets_expire_when_they_wait_beyond_ttl(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            packet_ttl=2,
        )
        env.inject_signal(count=1, cycle=0)

        env.tick(1)
        self.assertEqual(len(env.dropped_packets), 0)

        env.tick(2)
        self.assertEqual(len(env.inboxes["n0"]), 0)
        self.assertEqual(len(env.dropped_packets), 1)
        self.assertEqual(env.dropped_packets[0].drop_reason, "ttl_expired")

    def test_source_admission_rate_limits_ingress_to_source_inbox(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            source_admission_rate=1,
        )
        env.inject_signal(count=4, cycle=0)

        self.assertEqual(len(env.inboxes["n0"]), 1)
        self.assertEqual(len(env.source_buffer), 3)

        env.route_signal("n0", "sink", cost=0.05)
        env.prepare_cycle(1)
        self.assertEqual(len(env.inboxes["n0"]), 1)
        self.assertEqual(len(env.source_buffer), 2)

    def test_adaptive_admission_opens_under_healthy_backlog(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=3,
        )
        env.inject_signal(count=6, cycle=0)

        self.assertEqual(len(env.inboxes["n0"]), 2)
        self.assertEqual(env.last_source_admission, 2)

    def test_adaptive_admission_closes_when_source_is_dormant(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=3,
        )
        env.inject_signal(count=6, cycle=0)
        env.inboxes["n0"].clear()
        env.state_for("n0").atp = 0.0

        env.prepare_cycle(1)

        self.assertEqual(len(env.inboxes["n0"]), 0)
        self.assertGreater(len(env.source_buffer), 0)
        self.assertEqual(env.last_source_admission, 0)

    def test_admission_support_strengthens_after_successful_source_feedback(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        )
        env.inject_signal(count=1, cycle=0)
        before = env.admission_substrate.support

        env.prepare_cycle(1)
        env.route_signal("n0", "sink", cost=0.05)
        env.advance_feedback()
        env.tick(1)

        self.assertGreater(env.admission_substrate.support, before)
        self.assertGreater(env.last_source_efficiency, 0.0)

    def test_admission_support_weakens_after_unreciprocated_source_spend(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        )
        env.inject_signal(count=1, cycle=0)
        env.admission_substrate.support = 0.8
        before = env.admission_substrate.support

        env.prepare_cycle(1)
        env.route_signal("n0", "n1", cost=0.05)
        env.tick(1)

        self.assertLess(env.admission_substrate.support, before)
        self.assertLess(env.last_source_efficiency, 0.0)

    def test_route_signal_prioritizes_stalest_packet_in_local_queue(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.current_cycle = 5
        env.inboxes["n0"] = [
            SignalPacket(
                packet_id="fresh",
                origin="n0",
                target="sink",
                created_cycle=5,
                last_moved_cycle=5,
            ),
            SignalPacket(
                packet_id="stale",
                origin="n0",
                target="sink",
                created_cycle=0,
                last_moved_cycle=1,
            ),
        ]

        env.route_signal("n0", "sink", cost=0.05)

        self.assertEqual(env.delivered_packets[0].packet_id, "stale")

    def test_content_packet_survives_routing_to_sink(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_a",
        )

        env.route_signal("n0", "n1", cost=0.05)
        env.route_signal("n1", "sink", cost=0.05)

        delivered = env.delivered_packets[0]
        self.assertEqual(delivered.input_bits, [1, 0, 1, 1])
        self.assertEqual(delivered.payload_bits, [1, 0, 1, 1])
        self.assertEqual(delivered.context_bit, 1)
        self.assertEqual(delivered.task_id, "task_a")

    def test_route_signal_applies_transform_and_records_trace(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_a",
        )

        result = env.route_signal(
            "n0",
            "n1",
            cost=0.05,
            transform_name="rotate_left_1",
        )

        self.assertTrue(result["success"])
        packet = env.inboxes["n1"][0]
        self.assertEqual(packet.payload_bits, [0, 1, 1, 1])
        self.assertEqual(packet.transform_trace, ["rotate_left_1"])

    def test_runtime_state_restores_packet_content_fields(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 1, 0, 0]],
            context_bits=[0],
            task_id="task_a",
        )
        env.inboxes["n0"][0].transform_trace.append("identity")

        restored = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        restored.load_runtime_state(env.export_runtime_state())

        packet = restored.inboxes["n0"][0]
        self.assertEqual(packet.payload_bits, [1, 1, 0, 0])
        self.assertEqual(packet.input_bits, [1, 1, 0, 0])
        self.assertEqual(packet.context_bit, 0)
        self.assertEqual(packet.task_id, "task_a")
        self.assertEqual(packet.transform_trace, ["identity"])

    def test_sink_scores_exact_match_and_returns_full_feedback(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        result = env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="rotate_left_1",
        )

        packet = env.delivered_packets[0]
        self.assertTrue(packet.matched_target)
        self.assertEqual(packet.target_bits, [0, 1, 1, 1])
        self.assertEqual(packet.bit_match_ratio, 1.0)
        self.assertAlmostEqual(result["feedback_award"], env.feedback_amount, places=6)
        self.assertEqual(len(env.pending_feedback), 1)
        self.assertAlmostEqual(env.pending_feedback[0].amount, env.feedback_amount, places=6)

    def test_sink_scores_partial_match_with_smaller_feedback(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        result = env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="identity",
        )

        packet = env.delivered_packets[0]
        self.assertFalse(packet.matched_target)
        self.assertAlmostEqual(packet.bit_match_ratio, 0.5, places=6)
        self.assertGreater(result["feedback_award"], 0.0)
        self.assertLess(result["feedback_award"], env.feedback_amount)
        self.assertEqual(len(env.pending_feedback), 1)
        self.assertAlmostEqual(
            env.pending_feedback[0].amount,
            env.feedback_amount * 0.5,
            places=6,
        )

    def test_sink_scores_zero_match_with_no_feedback(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 0, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        result = env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="xor_mask_0101",
        )

        packet = env.delivered_packets[0]
        self.assertFalse(packet.matched_target)
        self.assertEqual(packet.bit_match_ratio, 0.0)
        self.assertEqual(result["feedback_award"], 0.0)
        self.assertEqual(packet.feedback_award, 0.0)
        self.assertEqual(env.pending_feedback, [])

    def test_sink_scores_task_b_exact_match(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )

        result = env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="xor_mask_0101",
        )

        packet = env.delivered_packets[0]
        self.assertTrue(packet.matched_target)
        self.assertEqual(packet.target_bits, [1, 1, 1, 0])
        self.assertAlmostEqual(result["feedback_award"], env.feedback_amount, places=6)

    def test_sink_scores_task_c_exact_match(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_c",
        )

        result = env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="xor_mask_1010",
        )

        packet = env.delivered_packets[0]
        self.assertTrue(packet.matched_target)
        self.assertEqual(packet.target_bits, [0, 0, 0, 1])
        self.assertAlmostEqual(result["feedback_award"], env.feedback_amount, places=6)

    def test_feedback_pulse_updates_transform_credit_on_returning_node(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="rotate_left_1",
        )

        delivered = env.advance_feedback()
        self.assertEqual(len(delivered), 1)
        observation = env.observe_local("n0")

        self.assertGreater(observation["feedback_credit_rotate_left_1"], 0.0)
        self.assertGreater(observation["last_match_ratio"], 0.0)
        self.assertGreater(observation["last_feedback_amount"], 0.0)

    def test_feedback_credit_is_bound_to_matching_context(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="rotate_left_1",
        )
        env.advance_feedback()

        env.inject_signal(
            count=1,
            cycle=1,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        observation_context0 = env.observe_local("n0")
        self.assertGreater(observation_context0["context_feedback_credit_rotate_left_1"], 0.0)

        env.inboxes["n0"].clear()
        env.inject_signal(
            count=1,
            cycle=2,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_a",
        )
        observation_context1 = env.observe_local("n0")
        self.assertEqual(observation_context1["context_feedback_credit_rotate_left_1"], 0.0)
        self.assertGreater(observation_context1["feedback_credit_rotate_left_1"], 0.0)

    def test_low_match_feedback_relaxes_stale_context_credit(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        state = env.state_for("n0")
        state.transform_credit["identity"] = 0.9
        state.context_transform_credit["identity:context_0"] = 0.8
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="identity",
        )
        env.advance_feedback()

        self.assertLess(state.transform_credit["identity"], 0.9)
        self.assertLess(state.context_transform_credit["identity:context_0"], 0.8)
        self.assertLess(state.context_transform_credit["identity:context_0"], 0.3)
        self.assertGreater(state.transform_debt["identity"], 0.0)
        self.assertGreater(state.context_transform_debt["identity:context_0"], 0.0)
        self.assertGreater(state.branch_transform_debt["sink:identity"], 0.0)
        self.assertGreater(state.context_branch_transform_debt["sink:identity:context_0"], 0.0)
        self.assertGreater(state.branch_context_debt["sink:context_0"], 0.0)

    def test_low_match_feedback_without_prior_commitment_does_not_build_large_debt(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="identity",
        )
        env.advance_feedback()
        state = env.state_for("n0")

        self.assertLessEqual(state.transform_debt.get("identity", 0.0), 1e-6)
        self.assertLessEqual(state.context_transform_debt.get("identity:context_0", 0.0), 1e-6)
        self.assertLessEqual(state.branch_transform_debt.get("sink:identity", 0.0), 1e-6)
        self.assertLessEqual(
            state.context_branch_transform_debt.get("sink:identity:context_0", 0.0),
            1e-6,
        )
        self.assertLessEqual(state.branch_context_debt.get("sink:context_0", 0.0), 1e-6)

    def test_good_match_feedback_clears_context_transform_debt(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        state = env.state_for("n0")
        state.transform_debt["rotate_left_1"] = 0.8
        state.context_transform_debt["rotate_left_1:context_0"] = 0.9
        state.branch_context_debt["sink:context_0"] = 0.7
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="rotate_left_1",
        )
        env.advance_feedback()

        self.assertLess(state.transform_debt["rotate_left_1"], 0.8)
        self.assertLess(state.context_transform_debt["rotate_left_1:context_0"], 0.9)
        self.assertLess(state.branch_context_debt["sink:context_0"], 0.7)
        self.assertGreater(state.branch_transform_credit["sink:rotate_left_1"], 0.0)
        self.assertGreater(
            state.context_branch_transform_credit["sink:rotate_left_1:context_0"],
            0.0,
        )
        self.assertGreater(state.branch_context_credit["sink:context_0"], 0.0)

    def test_aligned_partial_resolved_feedback_preserves_transform_credit(self) -> None:
        env = RoutingEnvironment(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            max_atp=1.0,
        )
        state = env.state_for("n0")
        state.transform_credit["identity"] = 0.6
        state.context_transform_credit["identity:context_3"] = 0.7
        state.branch_transform_credit["sink:identity"] = 0.5
        state.context_branch_transform_credit["sink:identity:context_3"] = 0.45
        state.branch_context_credit["sink:context_3"] = 0.5
        env.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[3],
            task_id="ceiling_c4_task_c",
        )

        env.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="identity",
        )
        env.pending_feedback[0].bit_match_ratio = 0.5
        delivered = env.advance_feedback()

        self.assertTrue(delivered[0]["transform_matches_context"])
        self.assertGreater(state.transform_credit["identity"], 0.35)
        self.assertGreater(state.context_transform_credit["identity:context_3"], 0.35)
        self.assertLessEqual(state.transform_debt.get("identity", 0.0), 1e-6)
        self.assertLessEqual(state.context_transform_debt.get("identity:context_3", 0.0), 1e-6)
        self.assertGreater(state.branch_transform_debt["sink:identity"], 0.0)
        self.assertGreater(state.context_branch_transform_debt["sink:identity:context_3"], 0.0)
        self.assertGreater(state.branch_context_debt["sink:context_3"], 0.0)


class TestNativeSubstrateSystem(unittest.TestCase):
    def test_local_observation_excludes_non_neighbors(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=7,
        )
        observation = system.environment.observe_local("n0")

        self.assertIn("progress_n1", observation)
        self.assertNotIn("progress_sink", observation)

    def test_local_observation_exposes_head_payload_without_target_bits(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
        )
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 1, 0, 1],
            context_bit=1,
            task_id="task_a",
            target_bits=[0, 1, 1, 0],
        )
        packet.transform_trace.append("identity")
        system.environment.inject_packets([packet], cycle=0)

        observation = system.environment.observe_local("n0")

        self.assertEqual(observation["has_packet"], 1.0)
        self.assertEqual(observation["payload_bit_0"], 1.0)
        self.assertEqual(observation["payload_bit_1"], 1.0)
        self.assertEqual(observation["payload_bit_2"], 0.0)
        self.assertEqual(observation["payload_bit_3"], 1.0)
        self.assertEqual(observation["head_has_context"], 1.0)
        self.assertEqual(observation["head_context_bit"], 1.0)
        self.assertGreater(observation["head_transform_depth"], 0.0)
        self.assertNotIn("target_bit_0", observation)

    def test_inject_signal_specs_preserves_task_metadata(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=29,
        )
        system.inject_signal_specs(
            [
                SignalSpec(
                    input_bits=[1, 0, 1, 0],
                    context_bit=1,
                    task_id="task_a",
                )
            ]
        )

        packet = system.environment.inboxes["n0"][0]
        self.assertEqual(packet.input_bits, [1, 0, 1, 0])
        self.assertEqual(packet.payload_bits, [1, 0, 1, 0])
        self.assertEqual(packet.context_bit, 1)
        self.assertEqual(packet.task_id, "task_a")

    def test_available_actions_include_route_transform_variants(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=19,
        )
        system.environment.inject_signal(count=1, cycle=0, packet_payloads=[[1, 0, 0, 1]])

        available = system.agents["n0"].engine.actions.available_actions(history_size=0)

        self.assertIn("route:n1", available)
        self.assertIn("route_transform:n1:identity", available)
        self.assertIn("route_transform:n1:rotate_left_1", available)
        self.assertIn("route_transform:n1:xor_mask_1010", available)
        self.assertIn("route_transform:n1:xor_mask_0101", available)

    def test_route_transform_action_executes_through_backend(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=23,
        )
        system.environment.inject_signal(count=1, cycle=0, packet_payloads=[[1, 0, 1, 0]])

        outcome = system.agents["n0"].engine.actions.execute(
            "route_transform:n1:xor_mask_0101"
        )

        self.assertTrue(outcome.success)
        packet = system.environment.inboxes["n1"][0]
        self.assertEqual(packet.payload_bits, [1, 1, 1, 1])
        self.assertEqual(packet.transform_trace, ["xor_mask_0101"])

    def test_route_transform_execution_uses_context_shaped_cost(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=41,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        system.agents["n0"].substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=1.0,
            context_bit=0,
        )

        before_atp = system.environment.state_for("n0").atp
        expected_cost = system.agents["n0"].substrate.use_cost(
            "n1",
            "rotate_left_1",
            0,
        )

        outcome = system.agents["n0"].engine.actions.execute(
            "route_transform:n1:rotate_left_1"
        )

        self.assertTrue(outcome.success)
        self.assertAlmostEqual(outcome.cost_secs, expected_cost, places=6)
        self.assertAlmostEqual(
            before_atp - system.environment.state_for("n0").atp,
            expected_cost,
            places=6,
        )

    def test_dormant_node_only_rests(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=5,
        )
        agent = system.agents["n0"]
        system.environment.state_for("n0").atp = 0.0

        available = agent.engine.actions.available_actions(history_size=0)
        self.assertEqual(available, ["rest"])

    def test_system_smoke_run_records_cycles(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("n3",),
                "n2": ("n3",),
                "n3": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "n3": 2, "sink": 3},
            source_id="n0",
            sink_id="sink",
            selector_seed=11,
        )
        system.inject_signal(count=2)
        for _ in range(5):
            report = system.run_global_cycle()

        self.assertEqual(report["cycle"], 5)
        self.assertEqual(system.agents["n0"].cycle, 5)
        self.assertIn("snapshot", report)
        self.assertGreaterEqual(system.environment.snapshot()["delivered_packets"], 1)

    def test_selector_prefers_supported_route_when_packet_waits(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        system.environment.inject_signal(count=1)
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1",), value=0.8)

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertEqual(action, "route:n1")

    def test_selector_avoids_context_transform_with_high_feedback_debt(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=53,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1",), value=0.8)
        agent.substrate.seed_action_support(
            "n1",
            "xor_mask_1010",
            value=1.0,
            context_bit=1,
        )
        agent.substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        state = system.environment.state_for("n0")
        state.context_transform_debt["xor_mask_1010:context_1"] = 1.0
        state.transform_debt["xor_mask_1010"] = 0.8

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertNotEqual(action, "route_transform:n1:xor_mask_1010")

    def test_selector_avoids_branch_with_high_context_branch_debt(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=59,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.8)
        agent.substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.6,
            context_bit=1,
        )
        agent.substrate.seed_action_support(
            "n2",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        state = system.environment.state_for("n0")
        state.branch_transform_debt["n1:xor_mask_0101"] = 0.8
        state.context_branch_transform_debt["n1:xor_mask_0101:context_1"] = 1.0

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertNotEqual(action, "route_transform:n1:xor_mask_0101")

    def test_selector_avoids_branch_with_high_context_branch_debt_even_for_alternate_transform(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=61,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.8)
        agent.substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=0.65,
            context_bit=1,
        )
        agent.substrate.seed_action_support(
            "n2",
            "xor_mask_0101",
            value=0.40,
            context_bit=1,
        )
        state = system.environment.state_for("n0")
        state.branch_context_debt["n1:context_1"] = 1.0

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertNotEqual(action.split(":")[1], "n1")

    def test_selector_prefers_branch_with_positive_context_credit(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=67,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.6)
        agent.substrate.seed_action_support(
            "n1",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        agent.substrate.seed_action_support(
            "n2",
            "xor_mask_0101",
            value=0.45,
            context_bit=1,
        )
        state = system.environment.state_for("n0")
        state.branch_context_credit["n2:context_1"] = 1.0

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertEqual(action.split(":")[1], "n2")

    def test_selector_prefers_transform_with_positive_context_branch_credit(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=71,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1",), value=0.7)
        agent.substrate.seed_action_support("n1", "xor_mask_1010", value=0.45, context_bit=1)
        agent.substrate.seed_action_support("n1", "xor_mask_0101", value=0.45, context_bit=1)
        state = system.environment.state_for("n0")
        state.context_branch_transform_credit["n1:xor_mask_0101:context_1"] = 1.0

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertEqual(action, "route_transform:n1:xor_mask_0101")

    def test_selector_resolves_multi_candidate_conflict_toward_dominant_context_branch_evidence(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[1],
            task_id="task_b",
        )
        agent = system.agents["n0"]
        agent.substrate.seed_support(("n1", "n2"), value=0.78)
        agent.substrate.seed_action_support("n1", "rotate_left_1", value=0.82, context_bit=1)
        agent.substrate.seed_action_support("n1", "xor_mask_0101", value=0.76, context_bit=1)
        agent.substrate.seed_action_support("n2", "xor_mask_0101", value=0.74, context_bit=1)

        state = system.environment.state_for("n0")
        state.branch_context_debt["n1:context_1"] = 0.7
        state.context_branch_transform_debt["n1:rotate_left_1:context_1"] = 0.75
        state.context_branch_transform_debt["n1:xor_mask_0101:context_1"] = 0.6
        state.branch_context_credit["n2:context_1"] = 0.85
        state.context_branch_transform_credit["n2:xor_mask_0101:context_1"] = 0.95

        available = agent.engine.actions.available_actions(history_size=0)
        action, _ = agent.engine.selector.select(available, history=[])

        self.assertEqual(action, "route_transform:n2:xor_mask_0101")


    def test_consolidation_promotes_route_history_into_substrate(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=3,
        )
        agent = system.agents["n0"]
        edge_key = agent.substrate.edge_key("n1")

        for cycle in range(1, 9):
            agent.engine.memory.record(
                CycleEntry(
                    cycle=cycle,
                    action="route:n1",
                    mode="constraint",
                    state_before={"inbox_load": 1.0},
                    state_after={edge_key: 0.8},
                    dimensions={edge_key: 0.8},
                    coherence=0.82,
                    delta=0.05,
                    gco=GCOStatus.PARTIAL,
                    cost_secs=0.04,
                )
            )

        agent.engine._run_consolidation()
        self.assertGreaterEqual(agent.substrate.support("n1"), 0.32)
        self.assertGreaterEqual(len(agent.substrate.constraint_patterns), 1)

    def test_consolidation_promotes_transform_history_into_action_support(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=33,
        )
        agent = system.agents["n0"]

        for cycle in range(1, 9):
            agent.engine.memory.record(
                CycleEntry(
                    cycle=cycle,
                    action="route_transform:n1:rotate_left_1",
                    mode="constraint",
                    state_before={"head_context_bit": 0.0, "head_has_context": 1.0},
                    state_after={"reward_buffer": 0.8},
                    dimensions={"contextual_fit": 0.8},
                    coherence=0.81,
                    delta=0.06,
                    gco=GCOStatus.PARTIAL,
                    cost_secs=0.04,
                )
            )

        agent.engine._run_consolidation()
        self.assertEqual(
            agent.substrate.action_support("n1", "rotate_left_1"),
            0.0,
        )
        self.assertGreaterEqual(
            agent.substrate.action_support("n1", "rotate_left_1", 0),
            0.24,
        )
        self.assertLess(
            agent.substrate.action_support("n1", "rotate_left_1", 1),
            0.24,
        )

    def test_save_and_load_carryover_restores_node_state(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=9,
        )
        system.inject_signal(count=1)
        system.run_global_cycle()
        system.agents["n0"].substrate.seed_support(("n1",), value=0.55)
        system.environment.state_for("n0").reward_buffer = 0.22

        temp_dir = ROOT / "tests_tmp" / f"carryover_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            system.save_carryover(temp_dir)

            restored = NativeSubstrateSystem(
                adjacency={
                    "n0": ("n1",),
                    "n1": ("sink",),
                },
                positions={"n0": 0, "n1": 1, "sink": 2},
                source_id="n0",
                sink_id="sink",
                selector_seed=9,
            )
            loaded = restored.load_carryover(temp_dir)

            self.assertTrue(loaded)
            self.assertEqual(restored.global_cycle, system.global_cycle)
            self.assertAlmostEqual(
                restored.agents["n0"].substrate.support("n1"),
                system.agents["n0"].substrate.support("n1"),
                places=6,
            )
            self.assertAlmostEqual(
                restored.environment.state_for("n0").reward_buffer,
                system.environment.state_for("n0").reward_buffer,
                places=6,
            )
            self.assertEqual(
                len(restored.agents["n0"].engine.memory.entries),
                len(system.agents["n0"].engine.memory.entries),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_substrate_only_carryover_restores_support_without_episodic_history(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=12,
        )
        system.inject_signal(count=1)
        system.run_global_cycle()
        system.agents["n0"].substrate.seed_support(("n1",), value=0.62)

        temp_dir = ROOT / "tests_tmp" / f"substrate_only_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            system.save_substrate_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={
                    "n0": ("n1",),
                    "n1": ("sink",),
                },
                positions={"n0": 0, "n1": 1, "sink": 2},
                source_id="n0",
                sink_id="sink",
                selector_seed=12,
            )
            loaded = restored.load_substrate_carryover(temp_dir)

            self.assertTrue(loaded)
            self.assertAlmostEqual(
                restored.agents["n0"].substrate.support("n1"),
                0.62,
                places=6,
            )
            self.assertEqual(restored.agents["n0"].engine.memory.entries, [])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_substrate_only_carryover_restores_promoted_context_action_support(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=43,
        )
        agent = system.agents["n0"]
        for _ in range(4):
            agent.substrate.record_context_feedback(
                "n1",
                "rotate_left_1",
                0,
                credit_signal=1.0,
                bit_match_ratio=1.0,
            )

        temp_dir = ROOT / "tests_tmp" / f"context_substrate_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            system.save_substrate_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={
                    "n0": ("n1",),
                    "n1": ("sink",),
                },
                positions={"n0": 0, "n1": 1, "sink": 2},
                source_id="n0",
                sink_id="sink",
                selector_seed=43,
            )
            loaded = restored.load_substrate_carryover(temp_dir)

            self.assertTrue(loaded)
            self.assertGreaterEqual(
                restored.agents["n0"].substrate.contextual_action_support(
                    "n1",
                    "rotate_left_1",
                    0,
                ),
                0.24,
            )
            self.assertEqual(
                restored.agents["n0"].substrate.contextual_action_support(
                    "n1",
                    "rotate_left_1",
                    1,
                ),
                0.0,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_summary_reports_packet_drops_under_strict_ttl(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=21,
            packet_ttl=1,
        )
        system.inject_signal(count=4)
        system.run_global_cycle()

        summary = system.summarize()
        self.assertGreaterEqual(summary["dropped_packets"], 1)
        self.assertGreater(summary["drop_ratio"], 0.0)

    def test_substrate_carryover_restores_admission_support(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=31,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        )
        system.inject_signal(count=1)
        system.run_global_cycle()
        learned_support = system.environment.admission_substrate.support

        temp_dir = ROOT / "tests_tmp" / f"admission_substrate_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            system.save_substrate_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={
                    "n0": ("sink",),
                },
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=31,
                source_admission_policy="adaptive",
                source_admission_min_rate=1,
                source_admission_max_rate=2,
            )
            loaded = restored.load_substrate_carryover(temp_dir)

            self.assertTrue(loaded)
            self.assertAlmostEqual(
                restored.environment.admission_substrate.support,
                learned_support,
                places=6,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_summary_reports_context_breakdown_and_action_supports(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=35,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        system.environment.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="rotate_left_1",
        )

        summary = system.summarize()

        self.assertIn("context_breakdown", summary)
        self.assertIn("context_0", summary["context_breakdown"])
        self.assertEqual(summary["context_breakdown"]["context_0"]["exact_matches"], 1)
        self.assertIn("final_transform_counts", summary)
        self.assertEqual(summary["final_transform_counts"]["rotate_left_1"], 1)
        self.assertIn("action_supports", summary)
        self.assertIn("context_action_supports", summary)
        self.assertIn("substrate_maintenance", summary)
        self.assertIn("n0", summary["substrate_maintenance"])

    def test_summary_reports_task_diagnostics_for_transform_mismatches(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=39,
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        system.environment.route_signal(
            "n0",
            "sink",
            cost=0.05,
            transform_name="identity",
        )

        summary = system.summarize()
        diagnostics = summary["task_diagnostics"]

        self.assertEqual(diagnostics["overall"]["identity_fallbacks"], 1)
        self.assertEqual(diagnostics["overall"]["wrong_transform_family"], 1)
        self.assertEqual(diagnostics["overall"]["route_right_transform_wrong"], 1)
        self.assertEqual(diagnostics["overall"]["route_wrong_transform_potentially_right"], 0)
        self.assertEqual(
            diagnostics["contexts"]["context_0"]["mismatch_transform_counts"]["identity"],
            1,
        )
        self.assertEqual(
            diagnostics["contexts"]["context_0"]["branch_counts"]["sink"],
            1,
        )


class TestScenarioCatalog(unittest.TestCase):
    def test_cvt1_stage1_scenario_is_available(self) -> None:
        scenarios = phase8_scenarios()
        scenario = scenarios["cvt1_task_a_stage1"]

        self.assertGreater(len(scenario.initial_signal_specs), 0)
        self.assertGreater(len(scenario.signal_schedule_specs or {}), 0)
        first_signal = scenario.initial_signal_specs[0]
        self.assertEqual(first_signal.task_id, "task_a")
        self.assertIsNotNone(first_signal.context_bit)

    def test_cvt1_task_b_stage1_scenario_is_available(self) -> None:
        scenarios = phase8_scenarios()
        scenario = scenarios["cvt1_task_b_stage1"]

        self.assertGreater(len(scenario.initial_signal_specs), 0)
        self.assertGreater(len(scenario.signal_schedule_specs or {}), 0)
        first_signal = scenario.initial_signal_specs[0]
        self.assertEqual(first_signal.task_id, "task_b")
        self.assertIsNotNone(first_signal.context_bit)

    def test_cvt1_task_c_stage1_scenario_is_available(self) -> None:
        scenarios = phase8_scenarios()
        scenario = scenarios["cvt1_task_c_stage1"]

        self.assertGreater(len(scenario.initial_signal_specs), 0)
        self.assertGreater(len(scenario.signal_schedule_specs or {}), 0)
        first_signal = scenario.initial_signal_specs[0]
        self.assertEqual(first_signal.task_id, "task_c")
        self.assertIsNotNone(first_signal.context_bit)


class TestTransferHarness(unittest.TestCase):
    def test_transfer_metrics_report_best_rolling_scores(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("sink",),
            },
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=47,
        )
        for cycle in range(8):
            system.environment.inject_signal(
                count=1,
                cycle=cycle,
                packet_payloads=[[1, 0, 1, 1]],
                context_bits=[0],
                task_id="task_a",
            )
            system.environment.route_signal(
                "n0",
                "sink",
                cost=0.05,
                transform_name="rotate_left_1",
            )
            system.global_cycle = cycle + 1

        metrics = transfer_metrics(system)

        self.assertTrue(metrics["criterion_reached"])
        self.assertEqual(metrics["examples_to_criterion"], 8)
        self.assertGreaterEqual(metrics["best_rolling_exact_rate"], 1.0)
        self.assertEqual(metrics["first_exact_match_example"], 1)
        self.assertEqual(metrics["first_expected_transform_example"], 1)
        self.assertEqual(metrics["first_sustained_expected_transform_example"], 1)
        self.assertEqual(metrics["early_window_wrong_transform_family"], 0)
        self.assertEqual(metrics["early_window_exact_rate"], 1.0)
        self.assertIn("anticipation", metrics)
        self.assertIn("predicted_route_entry_count", metrics["anticipation"])

    def test_transfer_aggregate_reports_context_and_error_diagnostics(self) -> None:
        results = [
            {
                "cold_task_b": {
                    "summary": {
                        "exact_matches": 1,
                        "mean_bit_accuracy": 0.4,
                        "mean_route_cost": 0.05,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 2,
                                "identity_fallbacks": 1,
                                "stale_context_support_suspicions": 1,
                            },
                            "contexts": {
                                "context_1": {"mean_bit_accuracy": 0.25},
                            },
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.25,
                        "early_window_wrong_transform_family_rate": 0.5,
                        "first_expected_transform_example": 4,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 0,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "warm_full_task_b": {
                    "summary": {
                        "exact_matches": 2,
                        "mean_bit_accuracy": 0.45,
                        "mean_route_cost": 0.04,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 1,
                                "identity_fallbacks": 0,
                                "stale_context_support_suspicions": 0,
                            },
                            "contexts": {
                                "context_1": {"mean_bit_accuracy": 0.5},
                            },
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.5,
                        "early_window_wrong_transform_family_rate": 0.25,
                        "first_expected_transform_example": 2,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 4,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "warm_substrate_task_b": {
                    "summary": {
                        "exact_matches": 3,
                        "mean_bit_accuracy": 0.5,
                        "mean_route_cost": 0.03,
                        "task_diagnostics": {
                            "overall": {
                                "wrong_transform_family": 0,
                                "identity_fallbacks": 0,
                                "stale_context_support_suspicions": 0,
                            },
                            "contexts": {
                                "context_1": {"mean_bit_accuracy": 0.625},
                            },
                        },
                    },
                    "transfer_metrics": {
                        "early_window_exact_rate": 0.625,
                        "early_window_wrong_transform_family_rate": 0.125,
                        "first_expected_transform_example": 1,
                        "anticipation": {
                            "recognized_source_transform_entry_count": 2,
                            "predicted_route_entry_count": 0,
                        },
                    },
                },
                "delta_full_task_b": {
                    "exact_matches": 1,
                    "mean_bit_accuracy": 0.05,
                    "mean_route_cost": -0.01,
                    "best_rolling_exact_rate": 0.125,
                    "best_rolling_bit_accuracy": 0.125,
                },
                "delta_substrate_task_b": {
                    "exact_matches": 2,
                    "mean_bit_accuracy": 0.1,
                    "mean_route_cost": -0.02,
                    "best_rolling_exact_rate": 0.25,
                    "best_rolling_bit_accuracy": 0.25,
                },
            }
        ]

        aggregate = aggregate_transfer(results)

        self.assertEqual(aggregate["avg_cold_task_b_context_1_bit_accuracy"], 0.25)
        self.assertEqual(aggregate["avg_warm_full_task_b_wrong_transform_family"], 1.0)
        self.assertEqual(aggregate["avg_warm_substrate_task_b_identity_fallbacks"], 0.0)
        self.assertEqual(aggregate["avg_cold_task_b_stale_support_suspicions"], 1.0)
        self.assertEqual(aggregate["avg_cold_task_b_early_exact_rate"], 0.25)
        self.assertEqual(aggregate["avg_warm_full_task_b_early_wrong_transform_family_rate"], 0.25)
        self.assertEqual(aggregate["avg_warm_full_task_b_first_expected_transform_example"], 2.0)
        self.assertEqual(aggregate["avg_warm_full_task_b_recognized_source_transform_entries"], 4.0)


class TestCapabilityControl(unittest.TestCase):
    def test_self_selected_source_can_track_latent_before_visible_context_is_suppressed(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=67,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )

        packet = system.environment.inboxes["n0"][0]

        self.assertTrue(system.environment._visible_context_exposed("n0", packet))
        self.assertTrue(system.environment._latent_tracker_engaged("n0", packet))

    def test_self_selected_visible_task_does_not_recruit_latent_immediately(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=69,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=5,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]] * 5,
            context_bits=[0] * 5,
            task_id="task_a",
        )

        system.run_global_cycle()
        capability = system.environment.capability_states["n0"]

        self.assertFalse(capability.latent_enabled)
        self.assertGreater(capability.visible_context_trust, 0.5)
        self.assertEqual(capability.latent_recruitment_cycles, [])

    def test_self_selected_summary_reports_capability_fields(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=71,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=1,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        system.run_global_cycle()

        summary = system.summarize()

        self.assertEqual(summary["capability_policy"], "self-selected")
        self.assertIn("capability_timeline", summary)
        self.assertTrue(summary["capability_timeline"])
        self.assertIn("capability_supports", summary)
        self.assertIn("n0", summary["capability_supports"])
        self.assertIn("latent_recruitment_cycles", summary)
        self.assertIn("growth_recruitment_cycles", summary)

    def test_self_selected_recent_latent_summary_persists_across_sparse_observations(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=72,
            capability_policy="self-selected",
        )
        tracker = system.environment.latent_context_trackers["n0"]
        state = tracker._state_for("task_a")
        assert state is not None
        state.dominant_context = 1
        state.confidence = 0.8
        state.total_evidence = 0.8
        state.last_observed_cycle = 6
        system.environment.current_cycle = 10

        recent = system.environment._recent_latent_task_summary("n0")

        self.assertEqual(recent["active"], 1.0)
        self.assertEqual(recent["task_age"], 4.0)
        self.assertGreater(recent["recency_weight"], 0.0)
        self.assertAlmostEqual(recent["confidence"], 0.8, places=6)

    def test_self_selected_carryover_restores_capability_state_without_oracle_fields(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
            capability_policy="self-selected",
        )
        capability = system.environment.capability_states["n0"]
        capability.latent_support = 0.73
        capability.latent_enabled = True
        capability.visible_context_trust = 0.18
        capability.growth_support = 0.61
        capability.growth_enabled = True
        capability.latent_recruitment_cycles = [2, 4]
        capability.growth_recruitment_cycles = [5]

        temp_dir = ROOT / "tests_tmp" / f"capability_state_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            system.save_memory_carryover(temp_dir)
            manifest_text = (temp_dir / "memory_state.json").read_text(encoding="utf-8")
            self.assertNotIn("benchmark_id", manifest_text)
            self.assertNotIn("oracle", manifest_text)

            restored = NativeSubstrateSystem(
                adjacency={"n0": ("sink",)},
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=73,
                capability_policy="self-selected",
            )
            self.assertTrue(restored.load_memory_carryover(temp_dir))
            restored_capability = restored.environment.capability_states["n0"]
            self.assertAlmostEqual(restored_capability.latent_support, 0.73, places=6)
            self.assertTrue(restored_capability.latent_enabled)
            self.assertAlmostEqual(restored_capability.growth_support, 0.61, places=6)
            self.assertTrue(restored_capability.growth_enabled)
            self.assertEqual(restored_capability.latent_recruitment_cycles, [2, 4])
            self.assertEqual(restored_capability.growth_recruitment_cycles, [5])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_self_selected_local_contradiction_can_recruit_latent(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=79,
            capability_policy="self-selected",
        )
        system.environment.inject_signal(
            count=5,
            cycle=0,
            packet_payloads=[[1, 0, 1, 1]] * 5,
            context_bits=[0] * 5,
            task_id="task_a",
        )
        runtime = system.environment.state_for("n0")
        runtime.received_feedback = 1
        runtime.last_match_ratio = 0.0
        runtime.transform_debt["rotate_left_1"] = 0.9
        capability = system.environment.capability_states["n0"]
        capability.latent_support = 0.50

        system.environment.tick(1)
        updated = system.environment.capability_states["n0"]

        self.assertTrue(updated.latent_enabled)
        self.assertGreater(updated.latent_support, 0.41)
        self.assertLess(updated.visible_context_trust, 1.0)
        self.assertEqual(updated.latent_recruitment_cycles, [1])



class TestNeuralBaselineHarness(unittest.TestCase):
    def test_examples_to_criterion_can_optionally_require_bit_accuracy(self) -> None:
        exact_results = [True] * 7 + [False]
        bit_accuracy_results = [0.90] * 8

        self.assertEqual(examples_to_criterion(exact_results), 8)
        self.assertIsNone(
            examples_to_criterion(
                exact_results,
                bit_accuracy_results,
                bit_accuracy_threshold=0.95,
            )
        )

    def test_epoch_scan_aggregate_leaves_single_pass_metrics_unset(self) -> None:
        result = BaselineResult(
            variant="rnn-latent",
            seed=0,
            task_id="task_a",
            exact_matches=None,
            mean_bit_accuracy=None,
            examples_to_criterion=162,
            criterion_reached=True,
            per_example_exact=[],
            per_example_accuracy=[],
            losses=[],
        )

        aggregate = aggregate_neural_results([result])

        self.assertIsNone(aggregate["mean_exact_matches"])
        self.assertIsNone(aggregate["mean_bit_accuracy"])
        self.assertEqual(aggregate["criterion_rate"], 1.0)
        self.assertEqual(aggregate["mean_examples_to_criterion"], 162)


class TestMorphogenesis(unittest.TestCase):
    def _edge_growth_system(self) -> NativeSubstrateSystem:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=71,
            morphogenesis_config=MorphogenesisConfig(
                enabled=True,
                checkpoint_interval=6,
                max_dynamic_nodes=2,
                edge_prune_ticks=20,
            ),
        )
        node_spec = system.topology_state.node_specs["n0"]
        node_spec.surplus_streak = 3
        node_spec.positive_energy_streak = 3
        node_spec.net_energy_recent = 0.18
        node_spec.value_recent = 0.26
        state = system.environment.state_for("n0")
        state.reward_buffer = 0.35
        state.context_transform_debt["rotate_left_1:context_0"] = 1.0
        system.environment.current_cycle = 6
        system.global_cycle = 6
        return system

    def _node_growth_system(self) -> NativeSubstrateSystem:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1",),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 2, "sink": 3},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
            morphogenesis_config=MorphogenesisConfig(
                enabled=True,
                checkpoint_interval=6,
                max_dynamic_nodes=2,
                edge_prune_ticks=20,
            ),
        )
        node_spec = system.topology_state.node_specs["n0"]
        node_spec.surplus_streak = 3
        node_spec.positive_energy_streak = 3
        node_spec.net_energy_recent = 0.20
        node_spec.value_recent = 0.28
        state = system.environment.state_for("n0")
        state.reward_buffer = 0.4
        state.context_transform_debt["rotate_left_1:context_0"] = 1.0
        system.environment.current_cycle = 6
        system.global_cycle = 6
        return system

    def test_growth_observation_exposes_local_affordances_only(self) -> None:
        system = self._edge_growth_system()

        observation = system.environment.observe_local("n0")
        actions = system.environment.growth_action_specs("n0")

        self.assertIn("contradiction_pressure", observation)
        self.assertIn("growth_surplus_streak", observation)
        self.assertIn("growth_candidate_count", observation)
        self.assertNotIn("branch_feedback_credit_n2_identity", observation)
        self.assertTrue(any(spec["action"] == "bud_edge:n2" for spec in actions))

    def test_bud_edge_action_spends_atp_and_refreshes_neighbors(self) -> None:
        system = self._edge_growth_system()
        agent = system.agents["n0"]
        before_atp = system.environment.state_for("n0").atp

        outcome = agent.engine.memory_binding.execute_memory_action("bud_edge:n2", agent.substrate)
        events = system.topology_manager.apply_checkpoint(system, 6)
        system.rebuild_agents_from_topology()

        self.assertTrue(outcome.success)
        self.assertLess(system.environment.state_for("n0").atp, before_atp)
        self.assertTrue(any(event.event_type == "bud_edge" for event in events))
        self.assertTrue(system.topology_state.has_edge("n0", "n2"))
        self.assertIn("n2", system.agents["n0"].neighbor_ids)

    def test_bud_node_creates_real_agent_and_keeps_feedback_sequential(self) -> None:
        system = self._node_growth_system()
        agent = system.agents["n0"]

        outcome = agent.engine.memory_binding.execute_memory_action("bud_node:1:n2", agent.substrate)
        events = system.topology_manager.apply_checkpoint(system, 6)
        system.rebuild_agents_from_topology()

        self.assertTrue(outcome.success)
        bud_events = [event for event in events if event.event_type == "bud_node"]
        self.assertEqual(len(bud_events), 1)
        new_node_id = bud_events[0].created_node_id
        self.assertIsNotNone(new_node_id)
        assert new_node_id is not None
        self.assertIn(new_node_id, system.agents)
        self.assertIn(new_node_id, system.agents["n0"].neighbor_ids)
        self.assertEqual(system.agents[new_node_id].neighbor_ids, ("n2",))

        system.environment.inject_signal(
            count=1,
            cycle=6,
            packet_payloads=[[1, 0, 1, 1]],
            context_bits=[0],
            task_id="task_a",
        )
        cost0 = system.agents["n0"].substrate.use_cost(new_node_id)
        system.environment.route_signal("n0", new_node_id, cost0)
        cost1 = system.agents[new_node_id].substrate.use_cost("n2")
        system.environment.route_signal(new_node_id, "n2", cost1)
        cost2 = system.agents["n2"].substrate.use_cost("sink", "rotate_left_1", 0)
        system.environment.route_signal("n2", "sink", cost2, transform_name="rotate_left_1")

        first = system.environment.advance_feedback()
        second = system.environment.advance_feedback()
        third = system.environment.advance_feedback()

        self.assertEqual(first[0]["node_id"], "n2")
        self.assertEqual(second[0]["node_id"], new_node_id)
        self.assertEqual(third[0]["node_id"], "n0")

        summary = system.summarize()
        self.assertEqual(summary["dynamic_node_count"], 1)
        self.assertGreaterEqual(summary["bud_successes"], 1)
        self.assertGreater(summary["new_node_utilization"], 0.0)
        self.assertIsNotNone(summary["time_to_first_feedback"])

    def test_auto_prune_and_apoptosis_cleanup_dynamic_structures(self) -> None:
        system = self._node_growth_system()
        agent = system.agents["n0"]
        agent.engine.memory_binding.execute_memory_action("bud_node:1:n2", agent.substrate)
        events = system.topology_manager.apply_checkpoint(system, 6)
        system.rebuild_agents_from_topology()
        new_node_id = next(event.created_node_id for event in events if event.event_type == "bud_node")
        assert new_node_id is not None

        parent = system.agents["n0"]
        parent.substrate._inner.slow[parent.substrate.edge_key(new_node_id)] = 0.0
        system.topology_state.edge_specs[f"n0->{new_node_id}"].created_cycle = 0
        system.topology_manager.config.edge_prune_ticks = 6
        system.morphogenesis_config.edge_prune_ticks = 6
        system.environment.morphogenesis_config.edge_prune_ticks = 6

        system.environment.queue_growth_proposal(
            "n0",
            f"prune_edge:{new_node_id}",
            score=0.9,
            cost=0.0,
        )
        prune_events = system.topology_manager.apply_checkpoint(system, 12)
        system.rebuild_agents_from_topology()
        self.assertTrue(any(event.event_type == "prune_edge" for event in prune_events))
        self.assertNotIn(new_node_id, system.agents["n0"].neighbor_ids)

        system.topology_state.remove_edge(new_node_id, "n2")
        system.environment.sync_topology()
        system.refresh_agent_neighbors(new_node_id)
        system.topology_state.node_specs[new_node_id].dormant_ticks = 6
        system.topology_state.node_specs[new_node_id].negative_energy_streak = 6
        system.topology_state.node_specs[new_node_id].value_recent = -0.2
        system.environment.state_for(new_node_id).atp = 0.0

        apoptosis_events = system.topology_manager.apply_checkpoint(system, 18)
        system.rebuild_agents_from_topology()
        self.assertTrue(any(event.event_type == "apoptosis" for event in apoptosis_events))
        self.assertNotIn(new_node_id, system.agents)

    def test_enabled_morphogenesis_preserves_static_scaffold_edges(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=89,
            morphogenesis_config=MorphogenesisConfig(
                enabled=True,
                checkpoint_interval=6,
                max_dynamic_nodes=2,
                edge_prune_ticks=6,
            ),
        )
        for edge in system.topology_state.edge_specs.values():
            edge.created_cycle = 0

        events = system.topology_manager.apply_checkpoint(system, 12)
        system.rebuild_agents_from_topology()

        self.assertFalse(any(event.event_type == "prune_edge" for event in events))
        self.assertTrue(system.topology_state.has_edge("n0", "n1"))
        self.assertTrue(system.topology_state.has_edge("n0", "n2"))

    def test_growth_requires_positive_energy_budget(self) -> None:
        system = self._edge_growth_system()
        node_spec = system.topology_state.node_specs["n0"]
        node_spec.positive_energy_streak = 0
        node_spec.net_energy_recent = -0.12
        node_spec.value_recent = -0.05

        actions = system.environment.growth_action_specs("n0")

        self.assertFalse(any(action["action"].startswith("bud_") for action in actions))

    def test_grown_topology_restores_from_carryover(self) -> None:
        system = self._node_growth_system()
        agent = system.agents["n0"]
        agent.engine.memory_binding.execute_memory_action("bud_node:1:n2", agent.substrate)
        events = system.topology_manager.apply_checkpoint(system, 6)
        system.rebuild_agents_from_topology()
        new_node_id = next(event.created_node_id for event in events if event.event_type == "bud_node")
        assert new_node_id is not None

        temp_dir = ROOT / "tests_tmp" / f"morphogenesis_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            system.save_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={
                    "n0": ("n1",),
                    "n1": ("sink",),
                    "n2": ("sink",),
                },
                positions={"n0": 0, "n1": 1, "n2": 2, "sink": 3},
                source_id="n0",
                sink_id="sink",
                selector_seed=73,
                morphogenesis_config=MorphogenesisConfig(
                    enabled=True,
                    checkpoint_interval=6,
                    max_dynamic_nodes=2,
                ),
            )
            loaded = restored.load_carryover(temp_dir)

            self.assertTrue(loaded)
            self.assertIn(new_node_id, restored.topology_state.node_specs)
            self.assertIn(new_node_id, restored.agents)
            self.assertIn(new_node_id, restored.agents["n0"].neighbor_ids)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestMorphogenesisComparison(unittest.TestCase):
    def test_growth_evaluation_requires_earned_structure(self) -> None:
        fixed = {
            "exact_matches": 4,
            "mean_bit_accuracy": 0.5,
            "mean_route_cost": 0.1,
            "total_action_cost": 2.0,
            "bud_successes": 0,
            "dynamic_node_count": 0,
            "new_node_utilization": 0.0,
            "time_to_first_feedback": None,
            "mean_feedback_award": 0.2,
            "prune_events": 0,
        }
        unearned = {
            **fixed,
            "bud_successes": 1,
            "dynamic_node_count": 1,
            "new_node_utilization": 0.0,
            "time_to_first_feedback": None,
        }
        earned = {
            **fixed,
            "bud_successes": 1,
            "dynamic_node_count": 1,
            "new_node_utilization": 1.0,
            "time_to_first_feedback": 1.0,
            "exact_matches": 5,
        }
        cheaper_but_worse = {
            **earned,
            "exact_matches": 3,
            "mean_bit_accuracy": 0.45,
            "mean_route_cost": 0.08,
            "total_action_cost": 1.9,
        }

        self.assertFalse(growth_counts_as_earned(unearned))
        self.assertTrue(growth_counts_as_earned(earned))
        self.assertFalse(growth_counts_as_win(fixed, unearned))
        self.assertTrue(growth_counts_as_win(fixed, earned))
        self.assertFalse(growth_counts_as_win(fixed, cheaper_but_worse))

    def test_compare_growth_for_seed_reports_structural_metrics(self) -> None:
        record = compare_growth_for_seed(
            13,
            "cvt1_task_b_stage1",
            morphogenesis_config=MorphogenesisConfig(
                enabled=True,
                checkpoint_interval=6,
                max_dynamic_nodes=2,
                contradiction_threshold=0.2,
                overload_threshold=0.2,
                atp_surplus_threshold=0.4,
            ),
        )

        self.assertIn("fixed", record)
        self.assertIn("growth", record)
        self.assertIn("delta", record)
        self.assertIn("bud_successes", record["growth"]["summary"])
        self.assertGreaterEqual(record["growth"]["summary"]["bud_successes"], 1)

    def test_aggregate_growth_results_tracks_earned_and_win_rates(self) -> None:
        results = [
            {
                "fixed": {
                    "summary": {
                        "exact_matches": 4,
                        "mean_bit_accuracy": 0.5,
                        "mean_route_cost": 0.1,
                        "total_action_cost": 2.0,
                        "edge_count": 6,
                        "node_count": 5,
                    }
                },
                "growth": {
                    "summary": {
                        "exact_matches": 5,
                        "mean_bit_accuracy": 0.6,
                        "mean_route_cost": 0.08,
                        "total_action_cost": 1.9,
                        "node_count": 6,
                        "edge_count": 7,
                        "bud_successes": 1,
                        "prune_events": 0,
                        "apoptosis_events": 0,
                        "dynamic_node_count": 1,
                        "new_node_utilization": 1.0,
                        "time_to_first_feedback": 1.0,
                    },
                    "earned_growth": True,
                    "growth_win": True,
                },
                "delta": {
                    "exact_matches": 1,
                    "mean_bit_accuracy": 0.1,
                    "mean_route_cost": -0.02,
                    "total_action_cost": -0.1,
                    "bud_successes": 1,
                    "dynamic_node_count": 1,
                    "edge_count": 1,
                    "node_count": 1,
                },
            },
            {
                "fixed": {
                    "summary": {
                        "exact_matches": 4,
                        "mean_bit_accuracy": 0.5,
                        "mean_route_cost": 0.1,
                        "total_action_cost": 2.0,
                        "edge_count": 6,
                        "node_count": 5,
                    }
                },
                "growth": {
                    "summary": {
                        "exact_matches": 4,
                        "mean_bit_accuracy": 0.5,
                        "mean_route_cost": 0.11,
                        "total_action_cost": 2.1,
                        "node_count": 5,
                        "edge_count": 6,
                        "bud_successes": 0,
                        "prune_events": 0,
                        "apoptosis_events": 0,
                        "dynamic_node_count": 0,
                        "new_node_utilization": 0.0,
                        "time_to_first_feedback": None,
                    },
                    "earned_growth": False,
                    "growth_win": False,
                },
                "delta": {
                    "exact_matches": 0,
                    "mean_bit_accuracy": 0.0,
                    "mean_route_cost": 0.01,
                    "total_action_cost": 0.1,
                    "bud_successes": 0,
                    "dynamic_node_count": 0,
                    "edge_count": 0,
                    "node_count": 0,
                },
            },
        ]

        aggregate = aggregate_growth_results(results)

        self.assertEqual(aggregate["avg_growth_bud_successes"], 0.5)
        self.assertEqual(aggregate["earned_growth_rate"], 0.5)
        self.assertEqual(aggregate["growth_win_rate"], 0.5)


class TestLatentContextProbe(unittest.TestCase):
    def test_latent_signal_specs_hide_context_but_preserve_hidden_targets(self) -> None:
        initial, schedule = latent_signal_specs("cvt1_task_a_stage1")

        self.assertIsNotNone(initial[0].target_bits)
        self.assertIsNone(initial[0].context_bit)
        self.assertIsNotNone(schedule)
        assert schedule is not None
        first_scheduled = next(iter(schedule.values()))[0]
        self.assertIsNone(first_scheduled.context_bit)
        self.assertIsNotNone(first_scheduled.target_bits)

    def test_score_packet_uses_hidden_target_bits_without_visible_context(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=19,
        )
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[0, 0, 1, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )

        award = system.environment.score_packet(packet)

        self.assertGreater(award, 0.0)
        self.assertTrue(packet.matched_target)
        self.assertEqual(packet.bit_match_ratio, 1.0)

    def test_latent_observation_uses_local_history_without_exposing_targets(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=11,
            source_sequence_context_enabled=False,
        )
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        system.environment.inject_packets((packet,), cycle=0)
        baseline = system.environment.observe_local("n0")
        self.assertEqual(baseline["latent_context_available"], 0.0)
        self.assertEqual(baseline["effective_has_context"], 0.0)
        self.assertTrue(all("target" not in key for key in baseline))

        system.environment.route_signal(
            "n0",
            "sink",
            system.agents["n0"].substrate.use_cost("sink", "rotate_left_1"),
            transform_name="rotate_left_1",
        )
        system.environment.advance_feedback()
        followup = system.environment.create_packet(
            cycle=1,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        system.environment.inject_packets((followup,), cycle=1)
        observed = system.environment.observe_local("n0")

        self.assertGreater(observed["history_transform_evidence_rotate_left_1"], 0.0)
        self.assertGreaterEqual(observed["effective_has_context"], 0.0)
        self.assertEqual(observed["task_transform_affinity_rotate_left_1"], 1.0)
        self.assertEqual(observed["task_transform_affinity_xor_mask_1010"], 1.0)
        self.assertEqual(observed["task_transform_affinity_xor_mask_0101"], -1.0)
        self.assertEqual(observed["source_sequence_available"], 0.0)
        self.assertTrue(all("target" not in key for key in observed))

    def test_source_sequence_adapter_exposes_source_local_features_without_effective_context(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=12,
            source_sequence_context_enabled=True,
        )
        first_packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        second_packet = system.environment.create_packet(
            cycle=1,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        system.environment.inject_packets((first_packet,), cycle=0)
        system.environment.observe_local("n0")
        system.environment.inboxes["n0"].clear()
        system.environment.inject_packets((second_packet,), cycle=1)

        observed = system.environment.observe_local("n0")
        self.assertEqual(observed["effective_has_context"], 0.0)
        self.assertEqual(observed["source_sequence_available"], 1.0)
        self.assertEqual(observed["source_sequence_prev_parity"], 0.0)
        self.assertGreater(observed["source_sequence_context_confidence"], 0.0)
        self.assertGreater(observed["source_sequence_transform_hint_rotate_left_1"], 0.0)
        self.assertLess(observed["source_sequence_transform_hint_identity"], 0.0)
        self.assertEqual(observed["source_prev_bit_0"], 1.0)
        self.assertEqual(observed["source_delta_bit_0"], 0.0)

    def test_source_sequence_adapter_uses_source_buffer_focus_packet_for_b2_hidden_memory(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
            source_sequence_context_enabled=True,
        )
        packets = [
            system.environment.create_packet(
                cycle=index,
                input_bits=input_bits,
                payload_bits=input_bits,
                context_bit=None,
                task_id="ceiling_b2_task_a",
                target_bits=[0, 0, 0, 0],
            )
            for index, input_bits in enumerate(
                ([1, 0, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0]),
                start=0,
            )
        ]

        for cycle, packet in enumerate(packets):
            system.environment.current_cycle = cycle
            system.environment.source_buffer = [packet]
            observed = system.environment.observe_local("n0")

        self.assertEqual(observed["has_packet"], 1.0)
        self.assertEqual(observed["head_has_task"], 1.0)
        self.assertEqual(observed["source_sequence_available"], 1.0)
        self.assertEqual(observed["source_sequence_context_estimate"], 1.0)
        self.assertGreater(observed["source_sequence_transform_hint_xor_mask_1010"], 0.0)
        self.assertLess(
            observed["source_sequence_transform_hint_rotate_left_1"],
            observed["source_sequence_transform_hint_xor_mask_1010"],
        )

    def test_selector_uses_effective_context_when_explicit_context_is_hidden(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={
                "n0": ("n1", "n2"),
                "n1": ("sink",),
                "n2": ("sink",),
            },
            positions={"n0": 0, "n1": 1, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            selector_seed=7,
        )
        tracker = system.environment.latent_context_trackers["n0"]
        for cycle in range(1, 5):
            tracker.record_feedback(
                "task_b",
                "xor_mask_0101",
                bit_match_ratio=1.0,
                credit_signal=1.0,
            )
            system.environment.current_cycle = cycle
            tracker.observe_task("task_b", cycle)

        system.agents["n0"].substrate.seed_action_support("n2", "xor_mask_0101", value=0.6, context_bit=1)
        packet = system.environment.create_packet(
            cycle=5,
            input_bits=[1, 1, 0, 0],
            payload_bits=[1, 1, 0, 0],
            context_bit=None,
            task_id="task_b",
            target_bits=[1, 0, 0, 1],
        )
        system.environment.inject_packets((packet,), cycle=5)

        available = system.agents["n0"].engine.actions.available_actions(0)
        action, _ = system.agents["n0"].engine.selector.select(available, [])
        self.assertEqual(action, "route_transform:n2:xor_mask_0101")

    def test_observation_preserves_packet_context_when_visible_context_is_suppressed(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("n2",), "n2": ("sink",)},
            positions={"n0": 0, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            capability_policy="self-selected",
            selector_seed=11,
        )
        system.environment.capability_states["n2"].visible_context_trust = 0.10
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 1, 0, 0],
            payload_bits=[1, 1, 0, 0],
            context_bit=1,
            task_id="task_b",
            target_bits=[1, 0, 0, 1],
        )
        system.environment.inboxes["n2"] = [packet]

        observed = system.environment.observe_local("n2")

        self.assertEqual(observed["packet_has_context"], 1.0)
        self.assertEqual(observed["packet_context_bit"], 1.0)
        self.assertEqual(observed["head_has_context"], 0.0)
        self.assertEqual(observed["effective_has_context"], 0.0)
        self.assertGreater(observed["packet_context_confidence"], 0.0)
        self.assertLess(observed["packet_context_confidence"], 0.5)
        self.assertEqual(observed["expected_transform_xor_mask_0101"], 1.0)

    def test_selector_uses_packet_context_when_visible_context_is_suppressed(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("n2",), "n2": ("sink",)},
            positions={"n0": 0, "n2": 1, "sink": 2},
            source_id="n0",
            sink_id="sink",
            capability_policy="self-selected",
            selector_seed=17,
        )
        system.environment.capability_states["n2"].visible_context_trust = 0.10
        system.agents["n2"].substrate.seed_action_support(
            "sink",
            "xor_mask_0101",
            value=0.6,
            context_bit=1,
        )
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 1, 0, 0],
            payload_bits=[1, 1, 0, 0],
            context_bit=1,
            task_id="task_b",
            target_bits=[1, 0, 0, 1],
        )
        system.environment.inboxes["n2"] = [packet]

        available = system.agents["n2"].engine.actions.available_actions(0)
        action, _ = system.agents["n2"].engine.selector.select(available, [])

        self.assertEqual(action, "route_transform:sink:xor_mask_0101")

    def test_selector_prefers_task_compatible_transform_over_identity_under_hidden_context(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=29,
        )
        packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        system.environment.inject_packets((packet,), cycle=0)

        available = system.agents["n0"].engine.actions.available_actions(0)
        action, _ = system.agents["n0"].engine.selector.select(available, [])

        self.assertIn(
            action,
            {"route_transform:sink:rotate_left_1", "route_transform:sink:xor_mask_1010"},
        )

    def test_source_sequence_hint_prefers_expected_transform_family(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=31,
            source_sequence_context_enabled=True,
        )
        first_packet = system.environment.create_packet(
            cycle=0,
            input_bits=[1, 0, 0, 0],
            payload_bits=[1, 0, 0, 0],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 0, 1],
        )
        second_packet = system.environment.create_packet(
            cycle=1,
            input_bits=[1, 0, 0, 1],
            payload_bits=[1, 0, 0, 1],
            context_bit=None,
            task_id="task_a",
            target_bits=[0, 0, 1, 1],
        )
        system.environment.inject_packets((first_packet,), cycle=0)
        system.environment.observe_local("n0")
        system.environment.inboxes["n0"].clear()
        system.environment.inject_packets((second_packet,), cycle=1)
        system.agents["n0"].engine.selector.exploration_rate = 0.0

        available = system.agents["n0"].engine.actions.available_actions(0)
        action, _ = system.agents["n0"].engine.selector.select(available, [])

        self.assertEqual(action, "route_transform:sink:xor_mask_1010")

    def test_low_confidence_latent_feedback_does_not_promote_context_support(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=13,
        )
        agent = system.agents["n0"]

        agent.absorb_feedback(
            [
                {
                    "edge": "n0->sink",
                    "transform": "rotate_left_1",
                    "context_bit": None,
                    "context_promotion_ready": False,
                    "amount": system.environment.feedback_amount,
                    "bit_match_ratio": 1.0,
                }
            ]
        )

        self.assertEqual(
            agent.substrate.contextual_action_support("sink", "rotate_left_1", 0),
            0.0,
        )

    def test_stable_latent_feedback_can_promote_context_support(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=17,
        )
        tracker = system.environment.latent_context_trackers["n0"]
        snapshot = None
        for cycle in range(1, 5):
            tracker.record_feedback(
                "task_a",
                "rotate_left_1",
                bit_match_ratio=1.0,
                credit_signal=1.0,
            )
            system.environment.current_cycle = cycle
            snapshot = tracker.observe_task("task_a", cycle)
        assert snapshot is not None
        self.assertTrue(snapshot["promotion_ready"])

        event = {
            "edge": "n0->sink",
            "transform": "rotate_left_1",
            "context_bit": snapshot["estimate"],
            "context_promotion_ready": snapshot["promotion_ready"],
            "amount": system.environment.feedback_amount,
            "bit_match_ratio": 1.0,
        }
        for _ in range(4):
            system.agents["n0"].absorb_feedback([event])

        self.assertGreater(
            system.agents["n0"].substrate.contextual_action_support("sink", "rotate_left_1", 0),
            0.0,
        )

    def test_latent_tracker_snapshot_separates_route_and_feedback_channels(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=41,
        )
        tracker = system.environment.latent_context_trackers["n0"]
        tracker.record_route("task_a", "rotate_left_1", is_source=True)
        tracker.record_feedback(
            "task_a",
            "xor_mask_1010",
            bit_match_ratio=1.0,
            credit_signal=1.0,
            is_source=True,
        )

        snapshot = tracker.snapshot("task_a")

        self.assertGreater(snapshot["channel_context_confidence"]["source_route"], 0.0)
        self.assertGreater(snapshot["channel_context_confidence"]["source_feedback"], 0.0)
        self.assertGreater(
            snapshot["channel_transform_evidence"]["source_route"]["rotate_left_1"],
            0.0,
        )
        self.assertGreater(
            snapshot["channel_transform_evidence"]["source_feedback"]["xor_mask_1010"],
            0.0,
        )

    def test_source_feedback_reinforces_source_route_commitment(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=43,
        )
        tracker = system.environment.latent_context_trackers["n0"]
        tracker.record_route("task_a", "rotate_left_1", is_source=True)
        tracker.record_route("task_a", "xor_mask_1010", is_source=True)
        mixed_snapshot = tracker.snapshot("task_a")
        mixed_confidence = mixed_snapshot["channel_context_confidence"]["source_route"]

        tracker.record_feedback(
            "task_a",
            "rotate_left_1",
            bit_match_ratio=1.0,
            credit_signal=1.0,
            is_source=True,
        )
        reinforced_snapshot = tracker.snapshot("task_a")

        self.assertEqual(reinforced_snapshot["channel_context_estimate"]["source_route"], 0)
        self.assertGreater(
            reinforced_snapshot["channel_context_confidence"]["source_route"],
            mixed_confidence,
        )
        self.assertGreater(
            reinforced_snapshot["channel_transform_evidence"]["source_route"]["rotate_left_1"],
            reinforced_snapshot["channel_transform_evidence"]["source_route"]["xor_mask_1010"],
        )

    def test_consolidation_uses_effective_context_fields_for_latent_runs(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        pipeline = Phase8ConsolidationPipeline()
        entries = [
            CycleEntry(
                cycle=cycle,
                action="route_transform:n1:rotate_left_1",
                mode="constraint",
                state_before={
                    "head_has_context": 0.0,
                    "effective_has_context": 1.0,
                    "effective_context_bit": 0.0,
                    "effective_context_confidence": 0.9,
                    "context_promotion_ready": 1.0,
                },
                state_after={"reward_buffer": 0.7},
                dimensions={"contextual_fit": 0.8},
                coherence=0.8,
                delta=0.06,
                gco=GCOStatus.PARTIAL,
                cost_secs=0.04,
            )
            for cycle in range(1, 4)
        ]

        pipeline.consolidate(entries, substrate)

        self.assertGreater(
            substrate.contextual_action_support("n1", "rotate_left_1", 0),
            0.0,
        )

    def test_memory_carryover_restores_latent_tracker_state(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=23,
        )
        tracker = system.environment.latent_context_trackers["n0"]
        for cycle in range(1, 5):
            tracker.record_feedback(
                "task_b",
                "xor_mask_0101",
                bit_match_ratio=1.0,
                credit_signal=1.0,
            )
            system.environment.current_cycle = cycle
            tracker.observe_task("task_b", cycle)

        temp_dir = ROOT / "tests_tmp" / f"latent_carryover_{uuid.uuid4().hex}"
        try:
            system.save_memory_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={"n0": ("sink",)},
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=23,
            )
            restored.load_memory_carryover(temp_dir)
            snapshot = restored.environment.latent_context_trackers["n0"].snapshot("task_b")
            self.assertTrue(snapshot["available"])
            self.assertEqual(snapshot["estimate"], 1)
            self.assertGreater(snapshot["confidence"], 0.0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_transfer_adaptation_phase_only_applies_to_unseen_tasks_after_carryover(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=47,
        )
        system.environment.configure_transfer_regime(task_ids_seen=["task_a"], start_cycle=12)
        system.environment.current_cycle = 12

        self.assertEqual(
            system.environment.transfer_adaptation_phase("task_a", node_id="n0"),
            0.0,
        )
        self.assertGreater(
            system.environment.transfer_adaptation_phase("task_b", node_id="n0"),
            0.0,
        )
        self.assertEqual(
            system.environment.transfer_adaptation_phase("task_b", node_id="sink"),
            0.0,
        )

        system.environment.current_cycle = 12 + system.environment.transfer_adaptation_window
        self.assertEqual(
            system.environment.transfer_adaptation_phase("task_b", node_id="n0"),
            0.0,
        )

    def test_disabled_latent_transfer_split_suppresses_adaptation_phase(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=59,
            latent_transfer_split_enabled=False,
        )
        system.environment.configure_transfer_regime(task_ids_seen=["task_a"], start_cycle=2)
        system.environment.current_cycle = 2

        self.assertEqual(
            system.environment.transfer_adaptation_phase("task_b", node_id="n0"),
            0.0,
        )

    def test_observe_local_exposes_transfer_hidden_adaptation_fields(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=49,
        )
        system.environment.configure_transfer_regime(task_ids_seen=["task_a"], start_cycle=4)
        system.environment.current_cycle = 4
        hidden_packet = SignalPacket(
            packet_id="pkt-hidden-transfer",
            origin="src",
            target="sink",
            created_cycle=4,
            input_bits=[1, 0, 1, 0],
            task_id="task_b",
            context_bit=None,
        )
        system.environment.inject_packets([hidden_packet], cycle=4)

        source_observation = system.environment.observe_local("n0")
        self.assertEqual(source_observation["transfer_hidden_unseen_task"], 1.0)
        self.assertGreater(source_observation["transfer_adaptation_phase"], 0.0)
        self.assertGreater(
            source_observation["effective_context_threshold"],
            source_observation["latent_context_confidence"] * 0.0 + 0.55,
        )

    def test_selector_explores_more_during_hidden_transfer_adaptation(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=53,
        )
        selector = system.agents["n0"].engine.selector

        baseline = selector._local_exploration_rate(
            history=[],
            local_inbox=1,
            urgency=0.0,
            observation={
                "transfer_hidden_unseen_task": 0.0,
                "transfer_adaptation_phase": 0.0,
            },
        )
        adapted = selector._local_exploration_rate(
            history=[],
            local_inbox=1,
            urgency=0.0,
            observation={
                "transfer_hidden_unseen_task": 1.0,
                "transfer_adaptation_phase": 1.0,
            },
        )

        self.assertGreater(adapted, baseline)


class TestLatentTimecourseAnalysis(unittest.TestCase):
    def test_latent_timeline_summary_tracks_pre_effective_instability(self) -> None:
        records = [
            {
                "cycle": 1,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.30,
                "effective_has_context": 0.0,
                "effective_context_confidence": 0.0,
                "context_promotion_ready": 0.0,
                "context_growth_ready": 0.0,
                "source_sequence_context_confidence": 0.80,
                "source_route_context_confidence": 0.60,
                "source_feedback_context_confidence": 0.10,
                "downstream_mean_route_context_confidence": 0.20,
                "downstream_mean_feedback_context_confidence": 0.15,
                "source_atp_ratio": 0.90,
                "delta_wrong_transform_family": 1.0,
                "delta_transform_unstable_across_inferred_context_boundary": 1.0,
                "delta_delayed_correction": 0.0,
                "delta_route_wrong_transform_potentially_right": 0.0,
                "delta_route_right_transform_wrong": 0.0,
                "mean_bit_accuracy": 0.25,
                "exact_matches": 0,
            },
            {
                "cycle": 2,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.72,
                "effective_has_context": 1.0,
                "effective_context_confidence": 0.72,
                "context_promotion_ready": 0.0,
                "context_growth_ready": 0.0,
                "source_sequence_context_confidence": 0.85,
                "source_route_context_confidence": 0.70,
                "source_feedback_context_confidence": 0.40,
                "downstream_mean_route_context_confidence": 0.30,
                "downstream_mean_feedback_context_confidence": 0.50,
                "source_atp_ratio": 0.70,
                "delta_wrong_transform_family": 0.0,
                "delta_transform_unstable_across_inferred_context_boundary": 1.0,
                "delta_delayed_correction": 1.0,
                "delta_route_wrong_transform_potentially_right": 1.0,
                "delta_route_right_transform_wrong": 0.0,
                "mean_bit_accuracy": 0.50,
                "exact_matches": 1,
            },
            {
                "cycle": 3,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.82,
                "effective_has_context": 1.0,
                "effective_context_confidence": 0.82,
                "context_promotion_ready": 1.0,
                "context_growth_ready": 1.0,
                "source_sequence_context_confidence": 0.90,
                "source_route_context_confidence": 0.80,
                "source_feedback_context_confidence": 0.20,
                "downstream_mean_route_context_confidence": 0.35,
                "downstream_mean_feedback_context_confidence": 0.55,
                "source_atp_ratio": 0.60,
                "delta_wrong_transform_family": 0.0,
                "delta_transform_unstable_across_inferred_context_boundary": 0.0,
                "delta_delayed_correction": 0.0,
                "delta_route_wrong_transform_potentially_right": 0.0,
                "delta_route_right_transform_wrong": 1.0,
                "mean_bit_accuracy": 0.75,
                "exact_matches": 2,
            },
        ]

        summary = _latent_timeline_summary(records)

        self.assertEqual(summary["first_latent_context_available_cycle"], 1)
        self.assertEqual(summary["first_effective_context_cycle"], 2)
        self.assertEqual(summary["first_context_promotion_ready_cycle"], 3)
        self.assertEqual(summary["first_context_growth_ready_cycle"], 3)
        self.assertEqual(summary["low_confidence_cycle_count"], 1)
        self.assertEqual(summary["pre_effective_wrong_transform_events"], 1)
        self.assertEqual(summary["pre_effective_instability_events"], 1)
        self.assertEqual(summary["instability_event_count"], 2)
        self.assertEqual(summary["wrong_transform_event_count"], 1)
        self.assertEqual(summary["delayed_correction_event_count"], 1)
        self.assertEqual(summary["route_wrong_transform_potentially_right_event_count"], 1)
        self.assertEqual(summary["route_right_transform_wrong_event_count"], 1)
        self.assertAlmostEqual(summary["avg_source_route_context_confidence"], 0.7, places=5)
        self.assertAlmostEqual(summary["avg_source_feedback_context_confidence"], 0.23333, places=4)
        self.assertAlmostEqual(summary["avg_downstream_feedback_context_confidence"], 0.4, places=5)
        self.assertAlmostEqual(summary["final_mean_bit_accuracy"], 0.75, places=5)
        self.assertEqual(summary["final_exact_matches"], 2)

    def test_aggregate_latent_variant_exposes_selector_windows(self) -> None:
        base_timeline = [
            {
                "cycle": 1,
                "exact_matches": 0,
                "mean_bit_accuracy": 0.25,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.30,
                "effective_has_context": 0.0,
                "effective_context_confidence": 0.0,
                "source_sequence_context_confidence": 0.80,
                "source_route_context_confidence": 0.60,
                "source_feedback_context_confidence": 0.10,
                "downstream_mean_route_context_confidence": 0.20,
                "downstream_mean_feedback_context_confidence": 0.15,
                "source_atp_ratio": 0.90,
                "wrong_transform_family": 1.0,
                "delta_wrong_transform_family": 1.0,
                "delta_transform_unstable_across_inferred_context_boundary": 1.0,
                "delta_delayed_correction": 0.0,
                "route_count": 2,
                "rest_count": 0,
                "invest_count": 0,
                "route_branch_counts": {"n1": 2},
                "route_transform_counts": {"rotate_left_1": 2},
                "route_mode_counts": {"constraint": 2},
                "branch_transform_counts": {"n1:rotate_left_1": 2},
                "mean_route_coherence": 0.4,
                "mean_route_delta": 0.1,
            },
            {
                "cycle": 2,
                "exact_matches": 1,
                "mean_bit_accuracy": 0.50,
                "latent_context_available": 1.0,
                "latent_context_confidence": 0.72,
                "effective_has_context": 1.0,
                "effective_context_confidence": 0.72,
                "source_sequence_context_confidence": 0.85,
                "source_route_context_confidence": 0.70,
                "source_feedback_context_confidence": 0.40,
                "downstream_mean_route_context_confidence": 0.30,
                "downstream_mean_feedback_context_confidence": 0.50,
                "source_atp_ratio": 0.70,
                "wrong_transform_family": 1.0,
                "delta_wrong_transform_family": 0.0,
                "delta_transform_unstable_across_inferred_context_boundary": 1.0,
                "delta_delayed_correction": 1.0,
                "route_count": 1,
                "rest_count": 1,
                "invest_count": 0,
                "route_branch_counts": {"n2": 1},
                "route_transform_counts": {"xor_mask_1010": 1},
                "route_mode_counts": {"constraint": 1},
                "branch_transform_counts": {"n2:xor_mask_1010": 1},
                "mean_route_coherence": 0.5,
                "mean_route_delta": 0.2,
            },
        ]
        summary = _latent_timeline_summary(base_timeline)
        records = [
            {"timeline": base_timeline, "summary": summary},
            {"timeline": base_timeline, "summary": summary},
        ]

        aggregate = _aggregate_latent_variant(records)

        self.assertEqual(aggregate["aggregate_summary"]["avg_low_confidence_cycle_count"], 1.0)
        self.assertEqual(aggregate["aggregate_summary"]["avg_pre_effective_instability_events"], 1.0)
        self.assertEqual(aggregate["aggregate_summary"]["avg_instability_event_count"], 2.0)
        self.assertEqual(
            aggregate["low_confidence_selector_summary"]["route_transform_counts"]["rotate_left_1"],
            4,
        )
        self.assertEqual(
            aggregate["instability_selector_summary"]["route_transform_counts"]["xor_mask_1010"],
            2,
        )
        self.assertEqual(
            aggregate["pre_effective_selector_summary"]["route_branch_counts"]["n1"],
            4,
        )


class TestMarch17ExpansionHarnesses(unittest.TestCase):
    def test_large_topology_catalog_includes_expanded_scenarios(self) -> None:
        scenarios = phase8_scenarios()

        self.assertIn("cvt1_task_a_large", scenarios)
        self.assertIn("cvt1_task_b_large", scenarios)
        self.assertIn("cvt1_task_c_large", scenarios)
        self.assertEqual(scenarios["cvt1_task_a_large"].packet_ttl, 14)
        self.assertGreater(
            len(scenarios["cvt1_task_a_large"].signal_schedule_specs or {}),
            len(scenarios["cvt1_task_a_stage1"].signal_schedule_specs or {}),
        )

    def test_large_topology_harness_runs_single_seed(self) -> None:
        result = evaluate_large_topology(seeds=(13,))

        self.assertEqual(result["topology"], "cvt1_large (10 nodes, 5-hop paths)")
        self.assertIn("avg_task_b_cold_exact", result["aggregate"])
        self.assertIn("avg_delta_b_exact", result["aggregate"])

    def test_morphogenesis_large_harness_runs_single_seed(self) -> None:
        result = evaluate_morphogenesis_large(seeds=(13,))

        self.assertIn("transfer", result)
        self.assertIn("aggregate", result["transfer"])
        self.assertIn("avg_fixed_transfer_exact_matches", result["transfer"]["aggregate"])
        self.assertIn("avg_growth_transfer_exact_matches", result["transfer"]["aggregate"])

    def test_morphogenesis_large_latent_harness_runs_single_seed(self) -> None:
        result = evaluate_morphogenesis_large(seeds=(13,), latent_context=True)

        self.assertTrue(result["latent_context"])
        self.assertTrue(result["source_sequence_context_enabled"])
        self.assertTrue(result["latent_transfer_split_enabled"])
        self.assertIn("cvt1_task_a_large", result["scenarios"])

    def test_morphogenesis_large_paired_harness_runs_single_seed(self) -> None:
        result = evaluate_morphogenesis_large_paired(seeds=(13,))

        self.assertIn("visible", result)
        self.assertIn("latent", result)
        self.assertIn("comparison", result)
        self.assertIn("transfer", result["comparison"])

    def test_morphogenesis_large_mode_switched_harness_runs_single_seed(self) -> None:
        result = evaluate_morphogenesis_large_mode_switched(seeds=(13,))

        self.assertIn("all_visible", result)
        self.assertIn("all_latent", result)
        self.assertIn("visible_train_latent_transfer", result)
        self.assertIn("comparison", result)

    def test_morphogenesis_large_carryover_bridge_harness_runs_single_seed(self) -> None:
        result = evaluate_morphogenesis_large_carryover_bridge(seeds=(13,))

        self.assertIn("policies", result)
        self.assertIn("all_visible", result["policies"])
        self.assertIn("all_latent", result["policies"])
        self.assertIn("visible_train_latent_transfer", result["policies"])
        self.assertIn("comparison", result)

    def test_sequential_transfer_harness_runs_single_seed(self) -> None:
        result = evaluate_sequential_transfer(seeds=(13,))

        self.assertIn("aggregate", result)
        self.assertIn("avg_delta_c_from_warm_b_exact", result["aggregate"])
        self.assertIn("avg_delta_c_from_a_exact", result["aggregate"])

    def test_sequential_transfer_latent_harness_runs_single_seed(self) -> None:
        result = evaluate_sequential_transfer(seeds=(13,), latent_context=True)

        self.assertTrue(result["latent_context"])
        self.assertTrue(result["source_sequence_context_enabled"])
        self.assertTrue(result["results"][0]["latent_context"])
        self.assertIn("avg_delta_c_from_warm_b_exact", result["aggregate"])

    def test_cyclic_transfer_harness_runs_single_seed(self) -> None:
        result = evaluate_cyclic_transfer(seeds=(13,))

        self.assertEqual(result["task_sequence"], [
            "cvt1_task_a_stage1",
            "cvt1_task_b_stage1",
            "cvt1_task_c_stage1",
            "cvt1_task_a_stage1",
        ])
        self.assertIn("avg_delta_exact_matches", result["aggregate"])
        self.assertIn("avg_final_a_exact_matches", result["aggregate"])

    def test_cyclic_transfer_latent_harness_runs_single_seed(self) -> None:
        result = evaluate_cyclic_transfer(seeds=(13,), latent_context=True)

        self.assertTrue(result["latent_context"])
        self.assertTrue(result["source_sequence_context_enabled"])
        self.assertTrue(result["results"][0]["latent_context"])
        self.assertIn("avg_delta_mean_bit_accuracy", result["aggregate"])

    def test_morphogenesis_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis.json"
        try:
            result = evaluate_morphogenesis(seeds=(13,), output_path=output_path)

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis")
            self.assertEqual(manifest["seeds"], [13])
            self.assertIn("title", manifest)
            self.assertIn("timestamp", manifest)
            self.assertIn("metadata", manifest)
            self.assertEqual(manifest["result"]["transfer"]["aggregate"], result["transfer"]["aggregate"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_morphogenesis_large_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis_large.json"
        try:
            result = evaluate_morphogenesis_large(seeds=(13,), output_path=output_path)

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis_large")
            self.assertEqual(manifest["seeds"], [13])
            self.assertIn("title", manifest)
            self.assertIn("timestamp", manifest)
            self.assertIn("metadata", manifest)
            self.assertEqual(manifest["result"]["transfer"]["aggregate"], result["transfer"]["aggregate"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_morphogenesis_large_latent_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis_large_latent.json"
        try:
            result = evaluate_morphogenesis_large(
                seeds=(13,),
                latent_context=True,
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis_large")
            self.assertTrue(manifest["result"]["latent_context"])
            self.assertIn("title", manifest)
            self.assertTrue(manifest["metadata"]["latent_context"])
            self.assertEqual(manifest["result"]["transfer"]["aggregate"], result["transfer"]["aggregate"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_morphogenesis_large_paired_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis_large_paired.json"
        try:
            result = evaluate_morphogenesis_large_paired(
                seeds=(13,),
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis_large_paired")
            self.assertIn("title", manifest)
            self.assertIn("visible", manifest["result"])
            self.assertIn("latent", manifest["result"])
            self.assertEqual(
                manifest["result"]["comparison"]["transfer"],
                result["comparison"]["transfer"],
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_morphogenesis_large_mode_switched_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis_large_mode_switched.json"
        try:
            result = evaluate_morphogenesis_large_mode_switched(
                seeds=(13,),
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis_large_mode_switched")
            self.assertIn("title", manifest)
            self.assertIn("all_visible", manifest["result"])
            self.assertIn("all_latent", manifest["result"])
            self.assertIn("visible_train_latent_transfer", manifest["result"])
            self.assertEqual(
                manifest["result"]["comparison"]["switched_minus_latent"],
                result["comparison"]["switched_minus_latent"],
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_morphogenesis_large_carryover_bridge_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "morphogenesis_large_carryover_bridge.json"
        try:
            result = evaluate_morphogenesis_large_carryover_bridge(
                seeds=(13,),
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "morphogenesis_large_carryover_bridge")
            self.assertIn("title", manifest)
            self.assertIn("policies", manifest["result"])
            self.assertIn("all_visible", manifest["result"]["policies"])
            self.assertEqual(
                manifest["result"]["comparison"]["switched_full_minus_substrate"],
                result["comparison"]["switched_full_minus_substrate"],
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sequential_transfer_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "sequential_transfer.json"
        try:
            result = evaluate_sequential_transfer(
                seeds=(13,),
                latent_context=True,
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "sequential_transfer")
            self.assertEqual(manifest["seeds"], [13])
            self.assertTrue(manifest["latent_context"])
            self.assertIn("title", manifest)
            self.assertIn("timestamp", manifest)
            self.assertIn("metadata", manifest)
            self.assertEqual(manifest["result"]["aggregate"], result["aggregate"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_cyclic_transfer_manifest_writes_result_schema(self) -> None:
        temp_dir = ROOT / "tests_tmp" / f"manifest_{uuid.uuid4().hex}"
        output_path = temp_dir / "cyclic_transfer.json"
        try:
            result = evaluate_cyclic_transfer(
                seeds=(13,),
                latent_context=True,
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness"], "cyclic_transfer")
            self.assertEqual(manifest["seeds"], [13])
            self.assertTrue(manifest["latent_context"])
            self.assertIn("title", manifest)
            self.assertEqual(manifest["result"]["aggregate"], result["aggregate"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

