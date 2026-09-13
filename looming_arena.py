"""
Looming Arena: Natural environment with a dark sphere approaching the fly.

Features a realistic ground surface, gradient sky, directional sunlight,
and atmospheric fog. The sphere approaches once (single loom) — when it
passes the fly, it disappears, letting the GF response decay naturally.
"""

import numpy as np
from flygym.arena import BaseArena
from terrarium_visuals import add_terrarium_shell, TERRARIUM_HALF_SIZE


class LoomingArena(BaseArena):
    """Arena with natural visuals and a looming threat sphere.

    Parameters
    ----------
    ball_radius : float
        Radius of the dark sphere in mm. Default 5.0.
    approach_speed : float
        Speed of approach in mm/s. Default 50.0.
    start_distance : float
        Initial distance of sphere from origin along +x in mm. Default 80.0.
    ball_height : float
        Height of sphere center above ground in mm. Default 2.0.
    """

    def __init__(self, ball_radius=5.0, approach_speed=50.0,
                 start_distance=80.0, ball_height=2.0, approach_angle=0.0,
                 taste_zones=None, odor_sources=None, ground_size=100):
        super().__init__()

        self.ball_radius = ball_radius
        self.approach_speed = approach_speed
        self.start_distance = start_distance
        self.ball_height = ball_height
        self.approach_angle = np.radians(approach_angle)
        self.ground_size = ground_size
        self.curr_time = 0.0
        self.interactive = False
        self._physics = None
        self._taste_zones = list(taste_zones or [])
        self._odor_sources = list(odor_sources or [])

        # Starting position
        self.ball_start = np.array([
            start_distance * np.cos(self.approach_angle),
            -start_distance * np.sin(self.approach_angle),
            ball_height,
        ])
        self.ball_pos = self.ball_start.copy()
        self._initial_positions = [self.ball_start.copy()]
        self._passed = False
        self._controls_added = False

        # Approach direction (toward origin, horizontal)
        direction = -self.ball_start.copy()
        direction[2] = 0.0
        norm = np.linalg.norm(direction[:2])
        self.approach_dir = (direction / norm if norm > 0
                             else np.array([1.0, 0.0, 0.0]))

        # ══════════════════════════════════════════════════════
        # VISUAL ENVIRONMENT
        # ══════════════════════════════════════════════════════

        # ── Neutral observation-room background ──
        self.root_element.asset.add(
            "texture",
            type="skybox",
            builtin="gradient",
            rgb1=(0.12, 0.15, 0.16),
            rgb2=(0.48, 0.52, 0.50),
            width=512,
            height=512,
        )

        # ── Headlight (warm ambient + directional) ──
        headlight = self.root_element.visual.headlight
        headlight.ambient = (0.42, 0.42, 0.40)
        headlight.diffuse = (0.62, 0.60, 0.56)
        headlight.specular = (0.12, 0.12, 0.12)

        # ── Sunlight (directional, warm) ──
        self.root_element.worldbody.add(
            "light",
            name="sun",
            pos=(0, 0, 200),
            dir=(0.4, 0.3, -1.0),
            diffuse=(0.82, 0.80, 0.72),
            specular=(0.18, 0.18, 0.16),
            castshadow=True,
            directional=True,
        )

        self._terrarium_mats = add_terrarium_shell(
            self.root_element, TERRARIUM_HALF_SIZE)
        self.friction = (1, 0.005, 0.0001)

        # ── Looming predator: a strong insect-like silhouette ──
        ball_mat = self.root_element.asset.add(
            "material",
            name="threat_ball",
            rgba=(0.035, 0.025, 0.045, 1.0),
            reflectance=0.15,
            specular=0.5,
            shininess=0.8,
        )
        self.object_body = self.root_element.worldbody.add(
            "body",
            name="looming_predator",
            mocap=True,
            pos=self.ball_start.tolist(),
            gravcomp=1,
        )
        self.object_body.add(
            "geom",
            name="looming_predator_abdomen", type="ellipsoid",
            size=(ball_radius, ball_radius * .62, ball_radius * .62),
            material=ball_mat,
        )
        self.object_body.add(
            "geom", name="looming_predator_head", type="sphere",
            size=(ball_radius * .48,), pos=(-ball_radius * .82, 0, 0),
            material=ball_mat)
        for side in (-1, 1):
            self.object_body.add(
                "geom", name=f"looming_predator_wing_{side}", type="ellipsoid",
                size=(ball_radius * .75, ball_radius * .12, ball_radius * .42),
                pos=(0, side * ball_radius * .75, ball_radius * .15),
                euler=(0, -.25, side * .35), rgba=(.12, .10, .15, .82))
        # Eight splayed legs make the looming stimulus read as a stylized
        # spider rather than an unexplained floating sphere.
        for side in (-1, 1):
            for j, x in enumerate((-3.2, -1.0, 1.2, 3.3)):
                y0 = side * ball_radius * .42
                y1 = side * ball_radius * (1.45 + .12 * (j % 2))
                self.object_body.add(
                    "geom", name=f"looming_predator_leg_{side}_{j}",
                    type="capsule", size=(ball_radius * .10,),
                    fromto=(x, y0, -.1, x + (j-1.5)*.35, y1, -ball_radius*.35),
                    material=ball_mat, conaffinity=0, contype=0)
        # ── Taste zones: crystal sugar and a contaminated dark-red patch ──
        _TASTE_LABELS = {'sugar': 'Sugar', 'bitter': 'Poison'}
        if taste_zones:
            _TASTE_COLORS = {
                'sugar':  (0.92, 0.86, 0.62, 0.92),
                'bitter': (0.38, 0.055, 0.045, 0.90),
            }
            for i, zone in enumerate(taste_zones):
                rgba = _TASTE_COLORS.get(zone.taste, (0.5, 0.5, 0.5, 0.4))
                mat = self.root_element.asset.add(
                    "material",
                    name=f"taste_mat_{i}",
                    rgba=rgba,
                    reflectance=0.15,
                    emission=0.05,
                )
                body = self.root_element.worldbody.add(
                    "body", name=f"taste_object_{i}", mocap=True,
                    pos=(zone.center[0], zone.center[1], 0.0))
                if zone.taste == 'sugar':
                    for j, (x, y, s) in enumerate(((-.9, 0, .75),
                                                   (.65, .45, .62),
                                                   (.3, -.8, .52),
                                                   (1.1, -.45, .38))):
                        body.add(
                            "geom", name=f"sugar_crystal_{i}_{j}", type="box",
                            size=(s, s, s), pos=(x, y, s),
                            euler=(.2, .35, .2*j), material=mat,
                            conaffinity=0, contype=0)
                else:
                    body.add("geom", name=f"poison_puddle_{i}", type="ellipsoid",
                             size=(2.8, 2.0, .16), pos=(0, 0, .16), material=mat,
                             conaffinity=0, contype=0)
                    for j, (x, y, s) in enumerate(((-.8, .5, .45),
                                                   (.7, -.3, .55),
                                                   (0, -.8, .32))):
                        body.add(
                            "geom", name=f"poison_bubble_{i}_{j}", type="sphere",
                            size=(s,), pos=(x, y, .15+s*.65),
                            rgba=(.12, .015, .02, 1),
                            conaffinity=0, contype=0)
                # Floating label site above zone
                label = _TASTE_LABELS.get(zone.taste, zone.taste.upper())
                body.add(
                    "site",
                    name=label,
                    pos=(0, 0, 2.0), size=(0.12,),
                    rgba=rgba[:3] + (1.0,),
                    group=3,
                )
                zone._arena_body = body
                self._initial_positions.append(zone.center.copy())

        # ── Odor sources: fruit morsel and distinctive warning source ──
        _ODOR_LABELS = {'attractive': 'Food', 'repulsive': 'Danger'}
        if odor_sources:
            _ODOR_COLORS = {
                'attractive': (0.82, 0.30, 0.08, 1.0),
                'repulsive':  (0.48, 0.10, 0.42, 1.0),
            }
            for i, src in enumerate(odor_sources):
                rgba = _ODOR_COLORS.get(
                    src.odor_type, (0.5, 0.5, 0.5, 0.5))
                # Solid core
                mat_core = self.root_element.asset.add(
                    "material",
                    name=f"odor_core_{i}",
                    rgba=rgba,
                    reflectance=0.3,
                    emission=0.05,
                    shininess=0.9,
                )
                body = self.root_element.worldbody.add(
                    "body", name=f"odor_object_{i}", mocap=True,
                    pos=src.position.tolist())
                if src.odor_type == 'attractive':
                    # A huge apple morsel at fly scale, with pale cut flesh,
                    # red peel and a leaf; its silhouette works without text.
                    body.add(
                        "geom", name=f"odor_source_{i}_fruit", type="ellipsoid",
                        size=(3.4, 2.4, 1.8), pos=(0, 0, 1.65),
                        material=mat_core, conaffinity=0, contype=0)
                    body.add("geom", name=f"fruit_flesh_{i}", type="ellipsoid",
                             size=(2.9, 2.05, 1.5), pos=(-.25, 0, 1.8),
                             rgba=(.94, .72, .34, 1), conaffinity=0, contype=0)
                    body.add(
                        "geom", name=f"fruit_leaf_{i}", type="ellipsoid",
                        size=(.9, .35, .10), pos=(.45, 0, 2.55),
                        euler=(0, .35, .2), rgba=(.16, .42, .08, 1),
                        conaffinity=0, contype=0)
                else:
                    # Stoppered laboratory vial with dark contents and a small
                    # fungus cluster communicates an aversive source.
                    body.add("geom", name=f"danger_vial_{i}", type="cylinder",
                             size=(1.25, 2.0), pos=(0, 0, 2.0), material=mat_core,
                             conaffinity=0, contype=0)
                    body.add("geom", name=f"danger_stopper_{i}", type="cylinder",
                             size=(.8, .35), pos=(0, 0, 4.25),
                             rgba=(.25, .14, .07, 1), conaffinity=0, contype=0)
                    for j, (x, y, s) in enumerate(((-1.2, .6, .55),
                                                   (1.0, .5, .42))):
                        body.add("geom", name=f"danger_clump_{i}_{j}", type="sphere",
                                 size=(s,), pos=(x, y, s), material=mat_core,
                                 conaffinity=0, contype=0)
                    body.add(
                        "geom", name=f"danger_spike_{i}", type="capsule",
                        size=(.35, 1.2), pos=(0, 0, 2.35), material=mat_core,
                        conaffinity=0, contype=0)
                # Translucent halo
                halo_rgba = (rgba[0], rgba[1], rgba[2], 0.15)
                mat_halo = self.root_element.asset.add(
                    "material",
                    name=f"odor_halo_{i}",
                    rgba=halo_rgba,
                    emission=0.8,
                )
                body.add(
                    "geom",
                    name=f"odor_halo_{i}_{src.odor_type}",
                    type="sphere",
                    size=(2.5,),
                    pos=(0, 0, 0.5),
                    material=mat_halo,
                    conaffinity=0,
                    contype=0,
                )
                # Floating label site above source
                label = _ODOR_LABELS.get(src.odor_type, src.odor_type.upper())
                body.add(
                    "site",
                    name=label,
                    pos=(0, 0, 3.0), size=(0.12,),
                    rgba=rgba[:3] + (1.0,),
                    group=3,
                )
                src._arena_body = body
                self._initial_positions.append(src.position.copy())

        # Selection feedback is independent of stimulus color and collision.
        marker_mat = self.root_element.asset.add(
            "material", name="selection_brass", rgba=(1, .72, .18, .85),
            emission=.12)
        self.selection_body = self.root_element.worldbody.add(
            "body", name="selection_marker", mocap=True,
            pos=self.ball_pos.tolist(), gravcomp=1)
        self.selection_body.add(
            "geom", name="selection_ring", type="cylinder",
            size=(3.5, .035), material=marker_mat, contype=0, conaffinity=0)
        self._selected_position = self.ball_pos

    def enable_interactive(self):
        """Enable manual control; screen-space help replaces world-space text."""
        self.interactive = True
        self._controls_added = True

    def set_selected_position(self, position):
        self._selected_position = position
        self.sync_interactive_objects()

    def get_spawn_position(self, rel_pos, rel_angle):
        return rel_pos, rel_angle

    def _get_max_floor_height(self):
        return 0.0

    def step(self, dt, physics, *args, **kwargs):
        """Move sphere toward fly; stop far behind after passing."""
        self._physics = physics
        if not self.interactive and not self._passed:
            self.ball_pos[:3] += self.approach_dir * self.approach_speed * dt

            behind = np.dot(self.ball_pos[:2], self.ball_start[:2])
            dist_to_origin = np.linalg.norm(self.ball_pos[:2])
            if behind < 0 and dist_to_origin > self.ball_radius * 2:
                self._passed = True
                self.ball_pos = np.array([0.0, 0.0, -100.0])

        physics.bind(self.object_body).mocap_pos = self.ball_pos
        self.sync_interactive_objects()
        self.curr_time += dt

    def sync_interactive_objects(self):
        """Copy shared sensory-source positions to their visual mocap bodies."""
        if self._physics is None:
            return
        self._physics.bind(self.object_body).mocap_pos = self.ball_pos
        for zone in self._taste_zones:
            self._physics.bind(zone._arena_body).mocap_pos = (
                zone.center[0], zone.center[1], 0.0)
        for src in self._odor_sources:
            self._physics.bind(src._arena_body).mocap_pos = src.position
        if self._selected_position is None:
            self._physics.bind(self.selection_body).mocap_pos = (0, 0, -100)
        else:
            selected = np.asarray(self._selected_position)
            self._physics.bind(self.selection_body).mocap_pos = (
                selected[0], selected[1], 0.09)

    def reset_interactive_objects(self):
        """Restore the authored positions without resetting neural state."""
        self.ball_pos[:] = self._initial_positions[0]
        offset = 1
        for zone in self._taste_zones:
            zone.center[:] = self._initial_positions[offset]
            offset += 1
        for src in self._odor_sources:
            src.position[:] = self._initial_positions[offset]
            offset += 1
        self._passed = False
        self.sync_interactive_objects()
