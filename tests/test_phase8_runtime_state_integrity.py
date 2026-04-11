from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from phase8 import NativeSubstrateSystem


ROOT = Path(__file__).resolve().parents[1]


class TestPhase8RuntimeStateIntegrity(unittest.TestCase):
    def test_memory_carryover_restores_local_unit_growth_intent_and_c_task_mode(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            c_task_layer1_mode="communicative",
        )
        local = system.environment.local_unit_state_for("n0")
        local.context.transform_belief = {"rotate_left_1": 0.8}
        local.context.hypothesis_transform = "rotate_left_1"
        local.context.hypothesis_confidence = 0.74
        local.context.dominant_transform = "rotate_left_1"
        local.context.transform_confidence = 0.69
        local.context.preserve_mode = True
        local.context.preserve_pressure = 0.66
        local.context.reopen_pressure = 0.12
        local.context.contradiction_load = 0.08
        local.context.commitment_age = 3
        intent = system.environment.growth_intent_state_for("n0")
        intent.requested = True
        intent.request_cycle = 7
        intent.request_pressure = 0.58
        intent.authorization_state = "authorize"
        intent.blocked_reason = "authorization_missing"
        intent.blocked_streak = 2

        temp_dir = ROOT / "tests_tmp" / f"local_unit_memory_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            system.save_memory_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={"n0": ("sink",)},
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=19,
            )
            self.assertTrue(restored.load_memory_carryover(temp_dir))
            restored_local = restored.environment.local_unit_state_for("n0")
            restored_intent = restored.environment.growth_intent_state_for("n0")
            self.assertEqual(restored.environment.local_unit_mode, "pulse_local_unit")
            self.assertEqual(restored.environment.local_unit_preset, "c_hr_overlap_tuned_v1")
            self.assertEqual(restored.environment.c_task_layer1_mode, "communicative")
            self.assertEqual(restored_local.context.hypothesis_transform, "rotate_left_1")
            self.assertAlmostEqual(restored_local.context.hypothesis_confidence, 0.74, places=6)
            self.assertTrue(restored_local.context.preserve_mode)
            self.assertAlmostEqual(restored_local.context.preserve_pressure, 0.66, places=6)
            self.assertTrue(restored_intent.requested)
            self.assertEqual(restored_intent.request_cycle, 7)
            self.assertAlmostEqual(restored_intent.request_pressure, 0.58, places=6)
            self.assertEqual(restored_intent.authorization_state, "authorize")
            self.assertEqual(restored_intent.blocked_reason, "authorization_missing")
            self.assertEqual(restored_intent.blocked_streak, 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_substrate_carryover_restores_local_unit_growth_intent_and_c_task_mode(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
            local_unit_mode="pulse_local_unit",
            local_unit_preset="c_hr_overlap_tuned_v1",
            c_task_layer1_mode="communicative",
        )
        local = system.environment.local_unit_state_for("n0")
        local.context.hypothesis_transform = "xor_mask_1010"
        local.context.hypothesis_confidence = 0.67
        local.context.preserve_mode = True
        local.context.preserve_pressure = 0.61
        intent = system.environment.growth_intent_state_for("n0")
        intent.requested = True
        intent.request_pressure = 0.49
        intent.authorization_state = "hold"

        temp_dir = ROOT / "tests_tmp" / f"local_unit_substrate_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            system.save_substrate_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={"n0": ("sink",)},
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=19,
            )
            self.assertTrue(restored.load_substrate_carryover(temp_dir))
            restored_local = restored.environment.local_unit_state_for("n0")
            restored_intent = restored.environment.growth_intent_state_for("n0")
            self.assertEqual(restored.environment.local_unit_mode, "pulse_local_unit")
            self.assertEqual(restored.environment.local_unit_preset, "c_hr_overlap_tuned_v1")
            self.assertEqual(restored.environment.c_task_layer1_mode, "communicative")
            self.assertEqual(restored_local.context.hypothesis_transform, "xor_mask_1010")
            self.assertAlmostEqual(restored_local.context.hypothesis_confidence, 0.67, places=6)
            self.assertTrue(restored_local.context.preserve_mode)
            self.assertAlmostEqual(restored_local.context.preserve_pressure, 0.61, places=6)
            self.assertTrue(restored_intent.requested)
            self.assertAlmostEqual(restored_intent.request_pressure, 0.49, places=6)
            self.assertEqual(restored_intent.authorization_state, "hold")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_scrub_poisoned_runtime_state_clears_local_c_task_context_on_drop(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=29,
            c_task_layer1_mode="communicative",
        )
        local = system.environment.local_unit_state_for("n0")
        local.context.transform_belief = {"rotate_left_1": 0.8, "identity": 0.2}
        local.context.hypothesis_transform = "rotate_left_1"
        local.context.hypothesis_confidence = 0.76
        local.context.dominant_transform = "rotate_left_1"
        local.context.transform_confidence = 0.71
        local.context.preserve_mode = True
        local.context.preserve_pressure = 0.68
        local.context.reopen_pressure = 0.16
        local.context.contradiction_load = 0.21
        local.context.commitment_age = 4

        system.environment.scrub_poisoned_runtime_state(intensity="drop")

        self.assertEqual(local.context.transform_belief, {})
        self.assertIsNone(local.context.hypothesis_transform)
        self.assertAlmostEqual(local.context.hypothesis_confidence, 0.0, places=6)
        self.assertIsNone(local.context.dominant_transform)
        self.assertAlmostEqual(local.context.transform_confidence, 0.0, places=6)
        self.assertFalse(local.context.preserve_mode)
        self.assertAlmostEqual(local.context.preserve_pressure, 0.0, places=6)
        self.assertAlmostEqual(local.context.reopen_pressure, 0.0, places=6)
        self.assertAlmostEqual(local.context.contradiction_load, 0.0, places=6)
        self.assertEqual(local.context.commitment_age, 0)
