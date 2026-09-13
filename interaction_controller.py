"""GLFW adapter for terrarium keyboard and mouse interaction."""


class InteractionController:
    """Translate viewer events into world manipulation and sensory pokes.

    MuJoCo's passive viewer owns its GLFW callbacks.  The normal key callback
    is supplied at launch; mouse support is installed only when GLFW exposes
    the viewer window, and chains the viewer's original callback so native
    orbit/pan controls continue to work.
    """

    HELP = (
        "NUMPAD 0 select | 4/6/8/2 move | 7/9 down/up | 5 poke | Shift fast | "
        "Enter pause | +/- speed | 1 follow | 3 free/follow | . reset | / help"
    )

    # Keep every terrarium action on the numeric keypad.  Unlike Alt-letter
    # and function-key chords, these do not collide with Windows shortcuts or
    # MuJoCo's normal letter, camera, and visualization bindings.
    KEY_SELECT = 320       # GLFW_KEY_KP_0
    KEY_FOLLOW = 321       # GLFW_KEY_KP_1
    KEY_DOWN = 322         # GLFW_KEY_KP_2
    KEY_CAMERA = 323       # GLFW_KEY_KP_3
    KEY_LEFT = 324         # GLFW_KEY_KP_4
    KEY_POKE = 325         # GLFW_KEY_KP_5
    KEY_RIGHT = 326        # GLFW_KEY_KP_6
    KEY_LOWER = 327        # GLFW_KEY_KP_7
    KEY_UP = 328           # GLFW_KEY_KP_8
    KEY_RAISE = 329        # GLFW_KEY_KP_9
    KEY_RESET = 330        # GLFW_KEY_KP_DECIMAL
    KEY_HELP = 331         # GLFW_KEY_KP_DIVIDE
    KEY_DEBUG = 332        # GLFW_KEY_KP_MULTIPLY
    KEY_SLOWER = 333       # GLFW_KEY_KP_SUBTRACT
    KEY_FASTER = 334       # GLFW_KEY_KP_ADD
    KEY_PAUSE = 335        # GLFW_KEY_KP_ENTER

    def __init__(self, terrarium, camera=None):
        self.terrarium = terrarium
        self.camera = camera
        self._window = None
        self._owns_keyboard_callback = False

    def on_key(self, keycode, fast=False, alt=None):
        if self._window is not None and not fast:
            try:
                import glfw
                if not fast:
                    fast = (glfw.get_key(self._window, glfw.KEY_LEFT_SHIFT) ==
                            glfw.PRESS or
                            glfw.get_key(self._window, glfw.KEY_RIGHT_SHIFT) ==
                            glfw.PRESS)
            except ImportError:
                pass
        moves = {self.KEY_UP: (0, 1, 0), self.KEY_DOWN: (0, -1, 0),
                 self.KEY_LEFT: (-1, 0, 0), self.KEY_RIGHT: (1, 0, 0),
                 self.KEY_LOWER: (0, 0, -1), self.KEY_RAISE: (0, 0, 1)}
        if keycode == self.KEY_SELECT:
            self.terrarium.select_next()
        elif keycode == self.KEY_PAUSE:
            self.terrarium.paused = not self.terrarium.paused
        elif keycode == self.KEY_HELP:
            self.terrarium.show_help = not self.terrarium.show_help
        elif keycode == self.KEY_DEBUG:
            self.terrarium.show_debug = not self.terrarium.show_debug
        elif keycode in moves:
            self.terrarium.move_selected(*moves[keycode], fast=fast)
        elif keycode == self.KEY_POKE:
            self.terrarium.queue_poke()
        elif keycode == self.KEY_SLOWER:
            self.terrarium.slower()
        elif keycode == self.KEY_FASTER:
            self.terrarium.faster()
        elif keycode == self.KEY_RESET:
            self.terrarium.reset()
            if self.camera:
                self.camera.reset()
        elif keycode == self.KEY_FOLLOW and self.camera:
            self.camera.follow()
        elif keycode == self.KEY_CAMERA and self.camera:
            self.camera.toggle()
        else:
            return False
        self.update_window_title()
        return True

    def update_window_title(self):
        """Put the control reminder on the window that receives the keys."""
        if self._window is None:
            return
        try:
            import glfw
            state = "PAUSED" if self.terrarium.paused else f"{self.terrarium.speed:g}x"
            status = (f"Fly Terrarium | [{self.terrarium.selected_name}] | "
                      f"{state} | NUMPAD / controls")
            if self.terrarium.show_help:
                status = (f"Fly Terrarium | NUMPAD 0 select "
                          f"[{self.terrarium.selected_name}] | 4 6 8 2 move | "
                          f"7 9 height | 5 poke | Enter pause ({state}) | "
                          f"+ - speed | / hide")
            glfw.set_window_title(self._window, status)
        except (AttributeError, ImportError):
            pass

    def attach_mouse(self, viewer):
        """Best-effort viewer hook; safely leaves unsupported viewers alone."""
        try:
            import glfw
            window = viewer._window
            self._window = window
            previous_key = glfw.set_key_callback(window, None)

            # The chained GLFW adapter preserves MuJoCo's native handler for
            # every key not owned by the terrarium.
            self._owns_keyboard_callback = True

            def key_callback(win, key, scancode, action, mods):
                handled = False
                if action == glfw.PRESS:
                    handled = self.on_key(
                        key,
                        fast=bool(mods & glfw.MOD_SHIFT),
                    )
                # Do not also send terrarium keys to MuJoCo.  This ordering is
                # important: forwarding first caused native viewer actions to
                # fire even when the terrarium handled the key.
                if not handled and previous_key:
                    previous_key(win, key, scancode, action, mods)

            glfw.set_key_callback(window, key_callback)
            self.update_window_title()
            return True
        except (AttributeError, ImportError):
            return False
