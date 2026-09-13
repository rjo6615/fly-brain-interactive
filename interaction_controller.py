"""GLFW adapter for terrarium keyboard and mouse interaction."""


class InteractionController:
    """Translate viewer events into world manipulation and sensory pokes.

    MuJoCo's passive viewer owns its GLFW callbacks.  The normal key callback
    is supplied at launch; mouse support is installed only when GLFW exposes
    the viewer window, and chains the viewer's original callback so native
    orbit/pan controls continue to work.
    """

    HELP = (
        "TAB select object | WASD move | Q/E lower/raise | Shift faster\n"
        "Ctrl+left click or P poke (screen side selects JO side) | F follow | "
        "C free/follow | R camera reset | T terrarium reset\n"
        "Space pause | [ slower | ] faster | H help | ` debug | wheel zoom"
    )

    def __init__(self, terrarium, camera=None):
        self.terrarium = terrarium
        self.camera = camera
        self._window = None

    def on_key(self, keycode, fast=False):
        if self._window is not None and not fast:
            try:
                import glfw
                fast = (glfw.get_key(self._window, glfw.KEY_LEFT_SHIFT) ==
                        glfw.PRESS or
                        glfw.get_key(self._window, glfw.KEY_RIGHT_SHIFT) ==
                        glfw.PRESS)
            except ImportError:
                pass
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        moves = {"W": (0, 1, 0), "S": (0, -1, 0),
                 "A": (-1, 0, 0), "D": (1, 0, 0),
                 "Q": (0, 0, -1), "E": (0, 0, 1)}
        if key in moves:
            self.terrarium.move_selected(*moves[key], fast=fast)
        elif keycode == 258:  # GLFW TAB
            self.terrarium.select_next()
        elif keycode == 32:
            self.terrarium.paused = not self.terrarium.paused
        elif keycode == 91:
            self.terrarium.slower()
        elif keycode == 93:
            self.terrarium.faster()
        elif key == "P":
            self.terrarium.queue_poke()
        elif key == "H":
            self.terrarium.show_help = not self.terrarium.show_help
        elif key == "`":
            self.terrarium.show_debug = not self.terrarium.show_debug
        elif key == "T":
            self.terrarium.reset()
        elif key == "F" and self.camera:
            self.camera.follow()
        elif key == "C" and self.camera:
            self.camera.toggle()
        elif key == "R" and self.camera:
            self.camera.reset()

    def attach_mouse(self, viewer):
        """Best-effort mouse hooks; safely leaves unsupported viewers alone."""
        try:
            import glfw
            window = viewer._window
            self._window = window
            previous_button = glfw.set_mouse_button_callback(window, None)
            previous_scroll = glfw.set_scroll_callback(window, None)

            def button_callback(win, button, action, mods):
                if previous_button:
                    previous_button(win, button, action, mods)
                if (button == glfw.MOUSE_BUTTON_LEFT and action == glfw.PRESS
                        and mods & glfw.MOD_CONTROL):
                    x, _ = glfw.get_cursor_pos(win)
                    width, _ = glfw.get_window_size(win)
                    self.terrarium.queue_poke("left" if x < width / 2 else "right")

            def scroll_callback(win, xoffset, yoffset):
                if previous_scroll:
                    previous_scroll(win, xoffset, yoffset)
                if self.camera:
                    self.camera.zoom(yoffset)

            glfw.set_mouse_button_callback(window, button_callback)
            glfw.set_scroll_callback(window, scroll_callback)
            return True
        except (AttributeError, ImportError):
            return False
