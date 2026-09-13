"""Key-command adapter for terrarium interaction."""


class InteractionController:
    """Translate viewer events into world manipulation and sensory pokes.

    MuJoCo's supported ``launch_passive`` key callback is the only input path
    used here.  In particular, this class must not replace the viewer's private
    GLFW callback: doing that is unsupported and can crash the native viewer.
    """

    HELP = (
        "NUMPAD 0 select | 4/6/8/2 move | 7/9 down/up | 5 poke | "
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

    def on_key(self, keycode, fast=False):
        moves = {self.KEY_UP: (0, 1, 0), self.KEY_DOWN: (0, -1, 0),
                 self.KEY_LEFT: (-1, 0, 0), self.KEY_RIGHT: (1, 0, 0),
                 self.KEY_LOWER: (0, 0, -1), self.KEY_RAISE: (0, 0, 1)}
        if keycode == self.KEY_SELECT:
            self.terrarium.select_next()
        elif keycode == self.KEY_PAUSE:
            self.terrarium.paused = not self.terrarium.paused
        elif keycode == self.KEY_HELP:
            self.terrarium.show_help = not self.terrarium.show_help
            if self.camera:
                self.camera.viewer.opt.sitegroup[4] = self.terrarium.show_help
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
