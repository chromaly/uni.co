import math
import threading
import time

import pyautogui

pyautogui.PAUSE = 0

ACTIVE_LEFT = 0.20
ACTIVE_RIGHT = 0.80
ACTIVE_TOP = 0.15
ACTIVE_BOTTOM = 0.70

CURSOR_INTERVAL = 1 / 60
FOLLOW_TIME = 0.06
CURSOR_DEADZONE = 4 
TARGET_TIMEOUT = 0.30


class MouseController:
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()

        self._target = None
        self._target_time = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()

        self._thread = threading.Thread(
            target=self._animate,
            daemon=True
        )
        self._thread.start()
        
        self._left_held = False

    def move_with_hand(self, hand):
        # Tracking only updates the destination.
        if hand is None:
            self.left_up()
        with self._lock:
            if hand is None:
                self._target = None
                return

            palm = hand[9]

            x = (palm.x - ACTIVE_LEFT) / (
                ACTIVE_RIGHT - ACTIVE_LEFT
            )
            y = (palm.y - ACTIVE_TOP) / (
                ACTIVE_BOTTOM - ACTIVE_TOP
            )

            x = max(0, min(1, x))
            y = max(0, min(1, y))

            self._target = (
                x * (self.screen_width - 1),
                y * (self.screen_height - 1)
            )
            self._target_time = time.perf_counter()

    def _animate(self):
        current_x = None
        current_y = None
        previous_time = time.perf_counter()

        try:
            while not self._stop.is_set():
                tick_start = time.perf_counter()
                dt = tick_start - previous_time
                previous_time = tick_start

                with self._lock:
                    target = self._target
                    target_time = self._target_time

                if (
                    target is None
                    or tick_start - target_time > TARGET_TIMEOUT
                ):
                    # Stop following when tracking is lost.
                    current_x = None
                    current_y = None
                else:
                    if current_x is None:
                        current_x, current_y = pyautogui.position()

                    # Smooth consistently despite timing variations.
                    alpha = 1 - math.exp(-dt / FOLLOW_TIME)

                    dx = target[0] - current_x
                    dy = target[1] - current_y
                    distance = math.hypot(dx, dy)

                    if distance > CURSOR_DEADZONE:
                        # Follow only the movement outside the tolerance.
                        movement = (distance - CURSOR_DEADZONE) / distance
                        current_x += dx * movement * alpha
                        current_y += dy * movement * alpha

                    pyautogui.moveTo(
                        round(current_x),
                        round(current_y),
                        duration=0
                    )

                # Account for time already spent moving the mouse.
                remaining = CURSOR_INTERVAL - (
                    time.perf_counter() - tick_start
                )
                self._stop.wait(max(0, remaining))

        except pyautogui.FailSafeException:
            print("Cursor stopped: PyAutoGUI failsafe triggered.")
            self._stop.set()

    def left_click(self):
        pyautogui.click()

    def left_down(self):
        if not self._left_held:
            pyautogui.mouseDown(button="left")
            self._left_held = True

    def left_up(self):
        if self._left_held:
            pyautogui.mouseUp(button="left")
            self._left_held = False

    def scroll(self, steps):
        if steps:
            pyautogui.scroll(int(steps))
    def right_click(self):
        pyautogui.rightClick()

    def stop(self):
        self._stop.set()
        self._thread.join()