"""Native MuJoCo picking and camera-accurate terrarium dragging.

GLFW callbacks only enqueue input: MuJoCo model/data/scene access remains on the
simulation thread.  The viewer's callbacks are chained, so an empty left drag
still orbits and right/middle camera gestures retain their normal behaviour.
"""

import queue
import numpy as np


class MouseInteraction:
    HEIGHT_PER_NOTCH = 0.5

    def __init__(self, viewer, controller, debug=False):
        self.viewer, self.controller = viewer, controller
        self.debug = debug
        self.events = queue.SimpleQueue()
        self.dragging = False
        self._pending_left_pick = False
        self._left_input_down = False
        self._camera_left_active = False
        self._sim = self._viewer_impl(viewer)
        self.window = (getattr(self._sim, "_window", None) or
                       getattr(viewer, "_window", None))
        self.available = self.window is not None and self._sim is not None
        self.unavailable_reason = None if self.available else (
            "active passive-viewer GLFW window/scene is not exposed")
        if not self.available:
            self.glfw = None
            return
        import glfw
        self.glfw = glfw
        self._old_button = glfw.set_mouse_button_callback(self.window,
                                                          self._mouse_button)
        self._old_cursor = glfw.set_cursor_pos_callback(self.window,
                                                        self._cursor_pos)
        self._old_scroll = glfw.set_scroll_callback(self.window, self._scroll)

    @staticmethod
    def _viewer_impl(viewer):
        """Resolve the private renderer that actually owns GLFW and mjvScene."""
        value = getattr(viewer, "_sim", None)
        value = value() if callable(value) else value
        return value or getattr(viewer, "_viewer", None)

    def _log(self, message):
        if self.debug or self.controller.show_debug:
            print(f"[Terrarium input] {message}")

    def _mouse_button(self, window, button, action, mods):
        x, y = self.glfw.get_cursor_pos(window)
        self.events.put(("button", button, action, mods, x, y))
        if button == self.glfw.MOUSE_BUTTON_LEFT:
            self._pending_left_pick = action == self.glfw.PRESS
            self._left_input_down = action == self.glfw.PRESS
        self._log(f"Mouse {'down' if action == self.glfw.PRESS else 'released'}: "
                  f"x={x:.1f}, y={y:.1f}")
        # A left press cannot be passed to MuJoCo before the simulation thread
        # has picked it: doing so arms the native camera and makes an object
        # drag orbit the view as well.  ``poll`` replays the gesture only when
        # the press hit empty space.  Other buttons remain native.
        if (button != self.glfw.MOUSE_BUTTON_LEFT and
                self._old_button is not None):
            self._old_button(window, button, action, mods)

    def _cursor_pos(self, window, x, y):
        if self.dragging or self._left_input_down or self._pending_left_pick:
            self.events.put(("move", x, y))
        elif self._old_cursor is not None:
            self._old_cursor(window, x, y)

    def _scroll(self, window, xoffset, yoffset):
        if self.controller.selected is not None:
            self.events.put(("scroll", yoffset))
        elif self._old_scroll is not None:
            self._old_scroll(window, xoffset, yoffset)

    def _dimensions(self):
        # Cursor coordinates use logical window pixels; convert them before
        # passing normalized coordinates to the framebuffer-sized viewport.
        ww, wh = self.glfw.get_window_size(self.window)
        fw, fh = self.glfw.get_framebuffer_size(self.window)
        return ww, wh, fw, fh

    def _pick(self, x, y):
        """Return controller index selected by MuJoCo's depth-aware picker."""
        import mujoco
        ww, wh, _, _ = self._dimensions()
        if ww <= 0 or wh <= 0:
            return None
        scene = getattr(self._sim, "_scene", None)
        model = getattr(self._sim, "_model", None)
        data = getattr(self._sim, "_data", None)
        if scene is None or model is None or data is None:
            return None
        selpnt = np.zeros(3, dtype=np.float64)
        geomid = np.array([-1], dtype=np.int32)
        skinid = np.array([-1], dtype=np.int32)
        # mjv_select returns body id and fills the closest visible geom.  This
        # respects current camera, perspective, zoom, viewport and occlusion.
        mujoco.mjv_select(model, data, self.viewer.opt, ww / wh,
                          x / ww, 1.0 - y / wh, scene,
                          selpnt, geomid, skinid)
        self._log(f"Ray created; geom={int(geomid[0])}")
        if geomid[0] < 0:
            return None
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM,
                                 int(geomid[0])) or ""
        index = self.controller.index_for_geom(name)
        self._log(f"Hit object: {self.controller.objects[index][0] if index is not None else name}")
        return index

    def floor_point(self, x, y, plane_z=0.0):
        """Intersect the exact rendered camera ray with a horizontal plane."""
        ww, wh, _, _ = self._dimensions()
        scene = getattr(self._sim, "_scene", None)
        if scene is None or ww <= 0 or wh <= 0:
            return None
        cameras = scene.camera
        eye = (np.asarray(cameras[0].pos) + np.asarray(cameras[1].pos)) / 2
        forward = np.asarray(cameras[0].forward, dtype=float)
        up = np.asarray(cameras[0].up, dtype=float)
        right = np.cross(forward, up)
        fovy = float(getattr(self._sim._model.vis.global_, "fovy", 45.0))
        half_h = np.tan(np.radians(fovy) / 2)
        ray = (forward + (2*x/ww-1) * (ww/wh) * half_h * right +
               (2*(1-y/wh)-1) * half_h * up)
        if abs(ray[2]) < 1e-9:
            return None
        t = (plane_z-eye[2]) / ray[2]
        return None if t <= 0 else eye + t*ray

    def poll(self):
        if not self.available:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return
            if event[0] == "button":
                _, button, action, mods, x, y = event
                if button == self.glfw.MOUSE_BUTTON_RIGHT and action == self.glfw.PRESS:
                    self.controller.select(None); self.dragging = False
                elif button == self.glfw.MOUSE_BUTTON_LEFT:
                    if action == self.glfw.PRESS:
                        picked = self._pick(x, y)
                        self.controller.select(picked)
                        self.dragging = picked is not None
                        self._pending_left_pick = False
                        self._camera_left_active = picked is None
                        if self._camera_left_active and self._old_button:
                            self._old_button(self.window, button, action, mods)
                        self._log(f"Selected: {self.controller.selected_name}")
                    else:
                        self.dragging = False
                        if self._camera_left_active and self._old_button:
                            self._old_button(self.window, button, action, mods)
                        self._camera_left_active = False
            elif event[0] == "move":
                if self.dragging:
                    point = self.floor_point(event[1], event[2])
                    if point is not None:
                        self.controller.place_selected(point[0], point[1])
                        self._log(f"Dragging {self.controller.selected_name} to world "
                                  f"position: x={point[0]:.2f}, y={point[1]:.2f}, z={point[2]:.2f}")
                elif self._camera_left_active and self._old_cursor:
                    self._old_cursor(self.window, event[1], event[2])
            elif event[0] == "scroll" and self.controller.selected is not None:
                self.controller.adjust_selected_height(event[1] * self.HEIGHT_PER_NOTCH)
