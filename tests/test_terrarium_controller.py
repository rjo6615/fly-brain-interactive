import unittest
import queue
import numpy as np

from terrarium_controller import TerrariumController
from interaction_controller import InteractionController
from mouse_interaction import MouseInteraction


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
        self.controller.select(0)
        self.controller.move_selected(dx=-1, dy=1)
        np.testing.assert_allclose(self.arena.ball_pos, [8, 2, 2])
        self.assertEqual(self.arena.synced, 1)

    def test_selected_sources_share_sensory_position_arrays(self):
        self.assertTrue(self.controller.show_labels)
        self.controller.select(1)
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

    def test_picked_geom_names_map_to_shared_sensory_objects(self):
        self.assertEqual(self.controller.index_for_geom(
            "arena/looming_predator_leg_-1_2"), 0)
        self.assertEqual(self.controller.index_for_geom(
            "arena/sugar_crystal_0_2"), 1)
        self.assertEqual(self.controller.index_for_geom(
            "arena/odor_source_0_fruit"), 2)
        self.assertIsNone(self.controller.index_for_geom("arena/decor_pebble_a"))

    def test_floor_proximity_pick_has_large_whole_object_targets(self):
        self.assertEqual(self.controller.index_near(10.5, 1.0), 0)
        self.assertEqual(self.controller.index_near(2.0, 2.0), 1)
        self.assertEqual(self.controller.index_near(7.5, 4.0), 2)
        self.assertIsNone(self.controller.index_near(-20, 20))

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
        resets = []
        interaction = InteractionController(
            self.controller, reset_callback=lambda: resets.append(True))
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
        interaction.on_key(interaction.KEY_BACKSPACE)
        self.assertEqual(resets, [True])
        self.assertEqual(self.arena.reset_count, 1)


class MouseInteractionTests(unittest.TestCase):
    """The object gesture and native camera gesture must be exclusive."""

    def setUp(self):
        self.arena = Arena()
        self.sugar = Source('sugar', center=[1, 2])
        self.food = Source('food', position=[3, 4, 1])
        self.controller = TerrariumController(
            self.arena, [self.sugar], [self.food])

    def make_mouse(self, picked):
        mouse = MouseInteraction.__new__(MouseInteraction)
        mouse.available = True
        mouse.events = queue.SimpleQueue()
        mouse.dragging = False
        mouse._pending_left_pick = True
        mouse._left_input_down = True
        mouse._camera_left_active = False
        mouse.window = object()
        mouse.glfw = type("Glfw", (), {
            "MOUSE_BUTTON_LEFT": 0, "MOUSE_BUTTON_RIGHT": 1,
            "PRESS": 1})()
        mouse.controller = self.controller
        mouse.controller.show_debug = False
        mouse._pick = lambda x, y: picked
        mouse.floor_point = lambda x, y: np.array([x, y, 0.0])
        mouse._log = lambda message: None
        mouse.native_buttons = []
        mouse.native_moves = []
        mouse._old_button = lambda *args: mouse.native_buttons.append(args[1:])
        mouse._old_cursor = lambda *args: mouse.native_moves.append(args[1:])
        return mouse

    def test_object_drag_does_not_arm_native_camera(self):
        mouse = self.make_mouse(2)
        mouse.events.put(("button", 0, 1, 0, 10, 20))
        mouse.events.put(("move", 12, 24))
        mouse.events.put(("button", 0, 0, 0, 12, 24))
        mouse.poll()
        self.assertEqual(mouse.native_buttons, [])
        self.assertEqual(mouse.native_moves, [])
        np.testing.assert_allclose(self.food.position[:2], [12, 24])

    def test_empty_drag_is_replayed_to_native_camera(self):
        mouse = self.make_mouse(None)
        mouse.events.put(("button", 0, 1, 0, 10, 20))
        mouse.events.put(("move", 12, 24))
        mouse.events.put(("button", 0, 0, 0, 12, 24))
        mouse.poll()
        self.assertEqual([event[1] for event in mouse.native_buttons], [1, 0])
        self.assertEqual(mouse.native_moves, [(12, 24)])


class MouseInteractionTests(unittest.TestCase):
    """The object gesture and native camera gesture must be exclusive."""

    def setUp(self):
        self.arena = Arena()
        self.sugar = Source('sugar', center=[1, 2])
        self.food = Source('food', position=[3, 4, 1])
        self.controller = TerrariumController(
            self.arena, [self.sugar], [self.food])

    def make_mouse(self, picked):
        mouse = MouseInteraction.__new__(MouseInteraction)
        mouse.available = True
        mouse.events = queue.SimpleQueue()
        mouse.dragging = False
        mouse._pending_left_pick = True
        mouse._left_input_down = True
        mouse._camera_left_active = False
        mouse.window = object()
        mouse.glfw = type("Glfw", (), {
            "MOUSE_BUTTON_LEFT": 0, "MOUSE_BUTTON_RIGHT": 1,
            "PRESS": 1})()
        mouse.controller = self.controller
        mouse.controller.show_debug = False
        mouse._pick = lambda x, y: picked
        mouse.floor_point = lambda x, y: np.array([x, y, 0.0])
        mouse._log = lambda message: None
        mouse.native_buttons = []
        mouse.native_moves = []
        mouse._old_button = lambda *args: mouse.native_buttons.append(args[1:])
        mouse._old_cursor = lambda *args: mouse.native_moves.append(args[1:])
        return mouse

    def test_object_drag_does_not_arm_native_camera(self):
        mouse = self.make_mouse(2)
        mouse.events.put(("button", 0, 1, 0, 10, 20))
        mouse.events.put(("move", 12, 24))
        mouse.events.put(("button", 0, 0, 0, 12, 24))
        mouse.poll()
        self.assertEqual(mouse.native_buttons, [])
        self.assertEqual(mouse.native_moves, [])
        np.testing.assert_allclose(self.food.position[:2], [12, 24])

    def test_empty_drag_is_replayed_to_native_camera(self):
        mouse = self.make_mouse(None)
        mouse.events.put(("button", 0, 1, 0, 10, 20))
        mouse.events.put(("move", 12, 24))
        mouse.events.put(("button", 0, 0, 0, 12, 24))
        mouse.poll()
        self.assertEqual([event[1] for event in mouse.native_buttons], [1, 0])
        self.assertEqual(mouse.native_moves, [(12, 24)])


if __name__ == '__main__':
    unittest.main()
