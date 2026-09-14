import unittest

import numpy as np

from brain_body_bridge import BrainBodyBridge


class DecoderStub:
    def __init__(self, normalized=None, populations=None):
        self.normalized = normalized or {}
        self.populations = populations or {}

    def get_normalized(self, name):
        return self.normalized.get(name, 0.0)

    def get_pop_rate(self, name):
        return self.populations.get(name, 0.0)


class BrainBodyBridgeDriveTests(unittest.TestCase):
    def test_bitter_escape_does_not_reuse_stale_visual_turn_bias(self):
        decoder = DecoderStub({"GF_1": 1.0, "GF_2": 1.0})
        bridge = BrainBodyBridge(decoder)
        bridge.bitter_contact = True
        bridge.visual_threat_bias = 1.0
        bridge._mode_timer = bridge._min_mode_dur

        drive = bridge.compute_drive()

        self.assertEqual(bridge.mode, "escape")
        np.testing.assert_allclose(drive, [1.3, 1.3])
        self.assertEqual(bridge.threat_asym, 0.0)

    def test_visual_escape_remains_directional_without_bitter_contact(self):
        decoder = DecoderStub(
            {"GF_1": 1.0, "GF_2": 1.0},
            {"LPLC2_left": 100.0, "LPLC2_right": 0.0},
        )
        bridge = BrainBodyBridge(decoder)
        bridge._mode_timer = bridge._min_mode_dur

        drive = bridge.compute_drive()

        self.assertNotEqual(drive[0], drive[1])


if __name__ == "__main__":
    unittest.main()
