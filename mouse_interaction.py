"""Mouse picking and floor-plane dragging for the passive MuJoCo viewer.

MuJoCo's passive-viewer API exposes only a key callback.  This adapter installs
small GLFW callback *chains* (it does not replace native camera handling) and
queues raw events.  All model/world mutation and picking happens later on the
simulation thread.
"""

import queue
import numpy as np


class MouseInteraction:
    """Select projected terrarium objects and drag them over the z=0 plane."""

    PICK_RADIUS_PX = 34
    HEIGHT_PER_NOTCH = 0.5

    def __init__(self, viewer, controller):
        import glfw

        self.glfw = glfw
        self.viewer = viewer
        self.controller = controller
        self.window = viewer._window
        self.events = queue.SimpleQueue()
        self.dragging = False
        self._left_down = False
        self._old_button = glfw.set_mouse_button_callback(
            self.window, self._mouse_button)
        self._old_cursor = glfw.set_cursor_pos_callback(
            self.window, self._cursor_pos)
        self._old_scroll = glfw.set_scroll_callback(self.window, self._scroll)

    def _mouse_button(self, window, button, action, mods):
        x, y = self.glfw.get_cursor_pos(window)
        self.events.put(("button", button, action, mods, x, y))
        if button == self.glfw.MOUSE_BUTTON_LEFT:
            self._left_down = action == self.glfw.PRESS
        # Left/right belong to objects; middle-button viewer gestures survive.
        if (self._old_button is not None and
                button not in (self.glfw.MOUSE_BUTTON_LEFT,
                               self.glfw.MOUSE_BUTTON_RIGHT)):
            self._old_button(window, button, action, mods)

    def _cursor_pos(self, window, x, y):
        if self.dragging:
            self.events.put(("move", x, y))
        if self._old_cursor is not None and not self._left_down:
            self._old_cursor(window, x, y)

    def _scroll(self, window, xoffset, yoffset):
        if self._left_down:
            self.events.put(("scroll", yoffset))
        elif self._old_scroll is not None:
            self._old_scroll(window, xoffset, yoffset)

    def _camera_frame(self):
        cam = self.viewer.cam
        az, el = np.radians([cam.azimuth, cam.elevation])
        forward = np.array([np.cos(el) * np.cos(az),
                            np.cos(el) * np.sin(az), np.sin(el)])
        eye = np.asarray(cam.lookat, dtype=float) - cam.distance * forward
        right = np.cross(forward, (0., 0., 1.))
        right /= max(np.linalg.norm(right), 1e-9)
        up = np.cross(right, forward)
        return eye, forward, right, up

    def _dimensions(self):
        return self.glfw.get_framebuffer_size(self.window)

    def project(self, point):
        """Approximate the viewer's perspective projection in framebuffer px."""
        width, height = self._dimensions()
        eye, forward, right, up = self._camera_frame()
        delta = np.asarray(point, dtype=float) - eye
        depth = np.dot(delta, forward)
        if depth <= 0:
            return None
        focal = .5 * height / np.tan(np.radians(45) / 2)
        return np.array([width/2 + focal*np.dot(delta, right)/depth,
                         height/2 - focal*np.dot(delta, up)/depth])

    def floor_point(self, x, y):
        width, height = self._dimensions()
        eye, forward, right, up = self._camera_frame()
        focal = .5 * height / np.tan(np.radians(45) / 2)
        ray = forward + (x-width/2)/focal*right - (y-height/2)/focal*up
        if abs(ray[2]) < 1e-8:
            return None
        distance = -eye[2] / ray[2]
        return None if distance <= 0 else eye + distance * ray

    def _pick(self, x, y):
        candidates = []
        for index, (_, pos) in enumerate(self.controller.objects):
            xyz = np.pad(np.asarray(pos, dtype=float), (0, 3-len(pos)))
            screen = self.project(xyz)
            if screen is not None:
                candidates.append((np.linalg.norm(screen-(x, y)), index))
        if not candidates:
            return None
        distance, index = min(candidates)
        return index if distance <= self.PICK_RADIUS_PX else None

    def poll(self):
        """Apply queued mouse input; call only from the simulation thread."""
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return
            if event[0] == "button":
                _, button, action, _, x, y = event
                if button == self.glfw.MOUSE_BUTTON_RIGHT and action == self.glfw.PRESS:
                    self.controller.select(None)
                    self.dragging = False
                elif button == self.glfw.MOUSE_BUTTON_LEFT:
                    if action == self.glfw.PRESS:
                        self.controller.select(self._pick(x, y))
                        self.dragging = self.controller.selected is not None
                    else:
                        self.dragging = False
            elif event[0] == "move" and self.dragging:
                point = self.floor_point(event[1], event[2])
                if point is not None:
                    self.controller.place_selected(point[0], point[1])
            elif event[0] == "scroll" and self.dragging:
                self.controller.adjust_selected_height(
                    event[1] * self.HEIGHT_PER_NOTCH)
