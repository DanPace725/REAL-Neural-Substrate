from __future__ import annotations

import unittest

from real_core import RegulatorySignal, SettlementDecision
from scripts.debug_force_growth import ForcedGrowthRegulator


class _StaticRegulator:
    def regulate(self, history):
        return RegulatorySignal(
            growth_authorization="hold",
            decision_hint=SettlementDecision.CONTINUE,
            pressure_level=0.42,
            metadata={"source": "base"},
        )


class TestDebugForceGrowth(unittest.TestCase):
    def test_wrapper_overrides_growth_authorization_only(self) -> None:
        regulator = ForcedGrowthRegulator(_StaticRegulator(), "initiate")

        signal = regulator.regulate([])

        self.assertEqual(signal.growth_authorization, "initiate")
        self.assertEqual(signal.decision_hint, SettlementDecision.CONTINUE)
        self.assertAlmostEqual(signal.pressure_level, 0.42)
        self.assertEqual(signal.metadata["source"], "base")
        self.assertEqual(signal.metadata["debug_original_growth_authorization"], "hold")
        self.assertEqual(signal.metadata["debug_forced_growth_authorization"], "initiate")


if __name__ == "__main__":
    unittest.main()
