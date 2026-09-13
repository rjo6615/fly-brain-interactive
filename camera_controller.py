"""Stable follow/free camera modes for the MuJoCo passive viewer."""

import mujoco


class CameraController:
    def __init__(self, viewer, body_id):
        self.viewer = viewer
        self.body_id = body_id
        self.following = False
        self.reset(follow=body_id >= 0)
        self.keep_terrarium_visuals_clean()

    def reset(self, follow=None):
        if follow is not None:
            self.following = follow
        cam = self.viewer.cam
        cam.type = (mujoco.mjtCamera.mjCAMERA_TRACKING if self.following
                    else mujoco.mjtCamera.mjCAMERA_FREE)
        if self.body_id >= 0:
            cam.trackbodyid = self.body_id
        cam.distance = 18.0 if self.following else 55.0
        cam.azimuth = -120.0
        cam.elevation = -25.0

    def follow(self):
        self.following = True
        self.reset()

    def toggle(self):
        self.following = not self.following
        self.reset()
        self.keep_terrarium_visuals_clean()

    def zoom(self, direction):
        self.viewer.cam.distance = max(
            3.0, min(300.0, self.viewer.cam.distance * (0.85 ** direction)))

    def keep_terrarium_visuals_clean(self):
        """Undo MuJoCo's built-in ``C`` contact-force visualization toggle.

        The passive viewer handles its own shortcuts in addition to invoking
        our key callback.  MuJoCo assigns ``C`` to contact-force rendering,
        which can draw a huge yellow force cylinder over this millimetre-scale
        animal.  Terrarium mode assigns ``C`` to the requested camera toggle,
        so contact diagnostics must remain disabled after the native handler
        sees that same event.
        """
        flags = self.viewer.opt.flags
        flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = False
        flags[mujoco.mjtVisFlag.mjVIS_CONTACTPOINT] = False
