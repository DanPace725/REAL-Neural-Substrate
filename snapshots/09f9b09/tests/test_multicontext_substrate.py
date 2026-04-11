from __future__ import annotations

import unittest

from phase8.models import SignalPacket
from phase8.substrate import ConnectionSubstrate


class TestMultiContextSignalPacket(unittest.TestCase):
    def test_packet_preserves_nonbinary_context_labels(self) -> None:
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


class TestMultiContextSubstrate(unittest.TestCase):
    def test_substrate_registers_nonbinary_context_support(self) -> None:
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

    def test_substrate_state_restores_dynamic_context_support(self) -> None:
        substrate = ConnectionSubstrate(("n1",))
        substrate.seed_action_support(
            "n1",
            "rotate_left_1",
            value=0.4,
            context_bit=3,
        )

        restored = ConnectionSubstrate(("n1",))
        restored.load_state(substrate.save_state())

        self.assertIn(3, restored.supported_contexts)
        self.assertGreaterEqual(
            restored.contextual_action_support("n1", "rotate_left_1", 3),
            0.4,
        )


if __name__ == "__main__":
    unittest.main()
