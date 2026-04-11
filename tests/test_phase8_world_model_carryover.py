from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path

from phase8 import NativeSubstrateSystem


ROOT = Path(__file__).resolve().parents[1]


class TestPhase8WorldModelCarryover(unittest.TestCase):
    def test_world_model_state_survives_memory_carryover(self) -> None:
        system = NativeSubstrateSystem(
            adjacency={"n0": ("sink",)},
            positions={"n0": 0, "sink": 1},
            source_id="n0",
            sink_id="sink",
            selector_seed=73,
            capability_policy="self-selected",
        )
        system.world_model_state = {
            "last_top_hypothesis": "h2",
            "last_action": "handoff_commit",
            "hypotheses": {
                "h2": {"support": 0.72},
            },
        }

        temp_dir = ROOT / "tests_tmp" / f"phase8_world_model_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            system.save_memory_carryover(temp_dir)
            restored = NativeSubstrateSystem(
                adjacency={"n0": ("sink",)},
                positions={"n0": 0, "sink": 1},
                source_id="n0",
                sink_id="sink",
                selector_seed=19,
                capability_policy="self-selected",
            )
            self.assertTrue(restored.load_memory_carryover(temp_dir))
            self.assertEqual(restored.world_model_state["last_top_hypothesis"], "h2")
            self.assertEqual(restored.world_model_state["last_action"], "handoff_commit")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
