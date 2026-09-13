import unittest
import numpy as np

from terrarium_controller import TerrariumController
from interaction_controller import InteractionController


class Source:
    def __init__(self, label, position=None, center=None):
        self.label = label
        if position is not None:
            self.position = np.array(position, dtype=float)
        if center is not None:
            self.center = np.array(center, dtype=float)


class Arena:
    def __init__(self):
        self.ball_pos = np.array([10.0, 0.0, 2.0])
        self.synced = 0
        self.reset_count = 0

    def sync_interactive_objects(self):
        self.synced += 1

    def reset_interactive_objects(self):
        self.reset_count += 1

    def set_selected_position(self, position):
        self.selected_position = position


class TerrariumControllerTests(unittest.TestCase):
    def setUp(self):
        self.arena = Arena()
        self.sugar = Source('sugar', center=[1, 2])
        self.food = Source('food', position=[3, 4, 1])
        self.controller = TerrariumController(
            self.arena, [self.sugar], [self.food])

    def test_moves_selected_world_object(self):
        self.controller.move_selected(dx=-1, dy=1)
        np.testing.assert_allclose(self.arena.ball_pos, [8, 2, 2])
        self.assertEqual(self.arena.synced, 1)

    def test_selected_sources_share_sensory_position_arrays(self):
        self.controller.select_next()
        self.assertIs(self.arena.selected_position, self.sugar.center)
        self.controller.move_selected(dx=1)
        np.testing.assert_allclose(self.sugar.center, [3, 2])

    def test_mouse_style_selection_place_height_and_deselect(self):
        self.controller.select(2)
        self.controller.place_selected(99, -99)
        self.controller.adjust_selected_height(1.5)
        np.testing.assert_allclose(self.food.position, [30.5, -30.5, 2.5])
        self.controller.select(None)
        self.assertEqual(self.controller.selected_name, "NONE")
        self.assertIsNone(self.arena.selected_position)

    def test_poke_is_lateralized_transient_and_summates(self):
        self.controller.queue_poke('left', 0.4)
        self.assertEqual(self.controller.consume_poke_rates(0.1, 200), (80, 0))
        self.controller.queue_poke('right', 0.6)
        left, right = self.controller.consume_poke_rates(0.1, 200)
        self.assertEqual(left, 0)
        self.assertGreater(right, 120)
        self.controller.consume_poke_rates(0.1, 200)
        self.assertIsNone(self.controller.poke)

    def test_keyboard_object_nudging_remains_as_compatibility_fallback(self):
        interaction = InteractionController(self.controller)
        # Remains safe for users updating from the window-title implementation,
        # whose on_key method may still invoke this compatibility hook.
        self.assertIsNone(interaction.update_window_title())
        self.assertFalse(interaction.on_key(ord('W')))
        self.assertTrue(interaction.on_key(interaction.KEY_UP))
        interaction.on_key(interaction.KEY_PAUSE)
        interaction.on_key(interaction.KEY_FASTER)
        self.assertEqual(self.arena.ball_pos[1], 0)
        self.assertTrue(self.controller.paused)
        self.assertEqual(self.controller.speed, 2)


if __name__ == '__main__':
    unittest.main()
