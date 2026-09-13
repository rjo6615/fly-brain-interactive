"""Input-independent state and commands for the interactive terrarium.

This module deliberately manipulates arena objects, never the fly's actuators.
Keyboard and mouse adapters can therefore remain thin and testable.
"""

from dataclasses import dataclass
import time
import numpy as np


@dataclass
class Poke:
    """A short, lateralized mechanosensory pulse."""

    side: str = "both"
    strength: float = 0.65
    remaining: float = 0.18


class TerrariumController:
    """Own interactive selection, time controls, and transient pokes."""

    MOVE_STEP = 2.0

    def __init__(self, arena, taste_zones, odor_sources):
        self.arena = arena
        self.objects = [("PREDATOR", arena.ball_pos)]
        taste_names = {"sugar": "SUGAR", "bitter": "POISON"}
        odor_names = {"attractive": "FOOD", "repulsive": "DANGER"}
        self.objects += [
            (taste_names.get(getattr(z, "taste", ""), z.label.upper()), z.center)
            for z in taste_zones]
        self.objects += [
            (odor_names.get(getattr(s, "odor_type", ""), s.label.upper()),
             s.position) for s in odor_sources]
        self.selected = 0
        self.paused = False
        self.speed = 1.0
        self.show_help = False
        self.show_hud = True
        self.show_labels = False
        self.show_debug = False
        self.poke = None
        self.selection_changed_at = time.monotonic()
        if hasattr(arena, "set_selected_position"):
            arena.set_selected_position(self.objects[0][1])

    @property
    def selected_name(self):
        return self.objects[self.selected][0]

    def select_next(self):
        self.selected = (self.selected + 1) % len(self.objects)
        self.selection_changed_at = time.monotonic()
        if hasattr(self.arena, "set_selected_position"):
            self.arena.set_selected_position(self.objects[self.selected][1])

    @property
    def selection_notice_visible(self):
        return time.monotonic() - self.selection_changed_at < 1.6

    def move_selected(self, dx=0.0, dy=0.0, dz=0.0, fast=False):
        amount = self.MOVE_STEP * (4.0 if fast else 1.0)
        pos = self.objects[self.selected][1]
        pos[:2] += np.array([dx, dy]) * amount
        if len(pos) > 2:
            pos[2] = max(0.1, pos[2] + dz * amount)
        self.arena.sync_interactive_objects()

    def queue_poke(self, side="both", strength=0.65):
        # Repeated clicks summate, but remain a sensory rate rather than a
        # behavior command.
        if self.poke is not None:
            strength = min(1.0, strength + self.poke.strength * 0.5)
        self.poke = Poke(side, strength)

    def consume_poke_rates(self, dt, max_rate):
        left = right = 0.0
        if self.poke is not None:
            rate = self.poke.strength * max_rate
            left = rate if self.poke.side in ("left", "both") else 0.0
            right = rate if self.poke.side in ("right", "both") else 0.0
            self.poke.remaining -= dt
            if self.poke.remaining <= 0:
                self.poke = None
        return left, right

    def slower(self):
        self.speed = max(0.125, self.speed / 2.0)

    def faster(self):
        self.speed = min(8.0, self.speed * 2.0)

    def reset(self):
        self.arena.reset_interactive_objects()
        self.paused = False
        self.speed = 1.0
        self.poke = None
        self.selection_changed_at = time.monotonic()
        if hasattr(self.arena, "set_selected_position"):
            self.arena.set_selected_position(self.objects[self.selected][1])
