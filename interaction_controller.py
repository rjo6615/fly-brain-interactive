"""GLFW adapter for terrarium keyboard and mouse interaction."""


class InteractionController:
    """Translate viewer events into world manipulation and sensory pokes.

    MuJoCo's passive viewer owns its GLFW callbacks.  The normal key callback
    is supplied at launch; mouse support is installed only when GLFW exposes
    the viewer window, and chains the viewer's original callback so native
    orbit/pan controls continue to work.
    """

    HELP = (
        "F9 select | Alt+WASD move | Alt+Q/E lower/raise | Shift faster\n"
        "Ctrl+left click or Alt+P poke | Alt+F follow | Alt+C free/follow\n"
        "Alt+R camera reset | Alt+T objects reset | wheel native zoom\n"
        "F10 pause | Alt+- slower | Alt+= faster | F11 help | F12 debug"
    )

    # F9-F12 are unused by MuJoCo's simulator UI. Letter, number, Tab,
    # Space, bracket, and F1-F8 keys all have native viewer meanings.
    KEY_SELECT = 298
    KEY_PAUSE = 299
    KEY_HELP = 300
    KEY_DEBUG = 301

    def __init__(self, terrarium, camera=None):
        self.terrarium = terrarium
        self.camera = camera
        self._window = None
        self._owns_keyboard_callback = False

    def on_key(self, keycode, fast=False, alt=None):
        if self._window is not None and (not fast or alt is None):
            try:
                import glfw
                if not fast:
                    fast = (glfw.get_key(self._window, glfw.KEY_LEFT_SHIFT) ==
                            glfw.PRESS or
                            glfw.get_key(self._window, glfw.KEY_RIGHT_SHIFT) ==
                            glfw.PRESS)
                if alt is None:
                    alt = (glfw.get_key(self._window, glfw.KEY_LEFT_ALT) ==
                           glfw.PRESS or
                           glfw.get_key(self._window, glfw.KEY_RIGHT_ALT) ==
                           glfw.PRESS)
            except ImportError:
                pass
        alt = bool(alt)
        key = chr(keycode).upper() if 0 <= keycode < 256 else ""
        moves = {"W": (0, 1, 0), "S": (0, -1, 0),
                 "A": (-1, 0, 0), "D": (1, 0, 0),
                 "Q": (0, 0, -1), "E": (0, 0, 1)}
        if keycode == self.KEY_SELECT:
            self.terrarium.select_next()
        elif keycode == self.KEY_PAUSE:
            self.terrarium.paused = not self.terrarium.paused
        elif keycode == self.KEY_HELP:
            self.terrarium.show_help = not self.terrarium.show_help
        elif keycode == self.KEY_DEBUG:
            self.terrarium.show_debug = not self.terrarium.show_debug
        elif not alt:
            return False
        elif key in moves:
            self.terrarium.move_selected(*moves[key], fast=fast)
        elif key == "P":
            self.terrarium.queue_poke()
        elif key == "-":
            self.terrarium.slower()
        elif key in ("=", "+"):
            self.terrarium.faster()
        elif key == "T":
            self.terrarium.reset()
        elif key == "F" and self.camera:
            self.camera.follow()
        elif key == "C" and self.camera:
            self.camera.toggle()
        elif key == "R" and self.camera:
            self.camera.reset()
        else:
            return False
        return True

    def attach_mouse(self, viewer):
        """Best-effort mouse hooks; safely leaves unsupported viewers alone."""
        try:
            import glfw
            window = viewer._window
            self._window = window
            previous_key = glfw.set_key_callback(window, None)
            previous_button = glfw.set_mouse_button_callback(window, None)
            previous_scroll = glfw.set_scroll_callback(window, None)

            # launch_passive's public callback exposes only the key code. This
            # chained GLFW adapter preserves MuJoCo's handler and gives us the
            # modifier mask needed to distinguish Alt+terrarium commands.
            self._owns_keyboard_callback = True

            def key_callback(win, key, scancode, action, mods):
                if previous_key:
                    previous_key(win, key, scancode, action, mods)
                if action == glfw.PRESS:
                    self.on_key(
                        key,
                        fast=bool(mods & glfw.MOD_SHIFT),
                        alt=bool(mods & glfw.MOD_ALT),
                    )

            def button_callback(win, button, action, mods):
                is_poke = (button == glfw.MOUSE_BUTTON_LEFT and
                           action == glfw.PRESS and mods & glfw.MOD_CONTROL)
                if is_poke:
                    x, _ = glfw.get_cursor_pos(win)
                    width, _ = glfw.get_window_size(win)
                    self.terrarium.queue_poke("left" if x < width / 2 else "right")
                elif previous_button:
                    previous_button(win, button, action, mods)

            def scroll_callback(win, xoffset, yoffset):
                if previous_scroll:
                    previous_scroll(win, xoffset, yoffset)

            glfw.set_key_callback(window, key_callback)
            glfw.set_mouse_button_callback(window, button_callback)
            glfw.set_scroll_callback(window, scroll_callback)
            return True
        except (AttributeError, ImportError):
            return False
