import time
import math

from swipe_detector import SwipeDetector
from finger_tilt import measure_finger_tilt

# Clicking settings

CLICK_DOWN_DISTANCE = 0.04
CLICK_UP_DISTANCE = 0.04
CLICK_HOLD_TIME = 0.4

# Swiping settings
SWIPE_PHYSICAL_HAND = "left"
SWIPE_RESTING_BEND = 10

SWIPE_DIRECTIONS = (
    {"small_bend": "left", "deep_bend": "right"}
    if SWIPE_PHYSICAL_HAND == "left"
    else {"small_bend": "right", "deep_bend": "left"}
)

class GestureDetector:

    def __init__(self):

        # -------------------------
        # Left click state
        # -------------------------

        self.left_click_state = "ready"
        self.left_start_y = None
        self.left_lowest_y = None
        self.left_down_since = None

        # -------------------------
        # Right click state
        # -------------------------

        self.right_click_state = "ready"
        self.right_start_y = None
        self.right_lowest_y = None


        # -------------------------
        # Swipe state
        # -------------------------

        self.swipe_detector = SwipeDetector(
            resting_bend=SWIPE_RESTING_BEND
        )


    def detect(self, right_hand, left_hand, swipe_world=None):

        gestures = []


        # =========================
        # Right hand
        # =========================

        if right_hand is not None:

            self.detect_clicks(
                right_hand,
                gestures
            )

        else:

            self.reset_clicks()


        # =========================
        # Left hand
        # =========================

        if left_hand is not None:
            self.detect_swipes(swipe_world, gestures)
        else:
            self.reset_swipe()


        return gestures


    # =========================
    # Click detection
    # =========================

    def detect_clicks(self, right_hand, gestures):

        center_palm = right_hand[9]

        index_finger = right_hand[8]
        middle_finger = right_hand[12]


        current_index_y = (
            index_finger.y
            - center_palm.y
        )

        current_middle_y = (
            middle_finger.y
            - center_palm.y
        )


        # =========================
        # Left click
        # =========================

        # Left click / hold-to-drag
        now = time.monotonic()

        if self.left_click_state == "ready":
            if self.left_start_y is None:
                self.left_start_y = current_index_y

            if (
                current_index_y - self.left_start_y
                >= CLICK_DOWN_DISTANCE
            ):
                self.left_click_state = "down"
                self.left_lowest_y = current_index_y
                self.left_down_since = now

        elif self.left_click_state in ("down", "dragging"):
            self.left_lowest_y = max(
                self.left_lowest_y,
                current_index_y,
            )

            released = (
                self.left_lowest_y - current_index_y
                >= CLICK_UP_DISTANCE
            )

            if released:
                if self.left_click_state == "dragging":
                    gestures.append("left_up")
                else:
                    gestures.append("left_click")

                self.left_click_state = "ready"
                self.left_start_y = None
                self.left_lowest_y = None
                self.left_down_since = None

            elif (
                self.left_click_state == "down"
                and now - self.left_down_since >= CLICK_HOLD_TIME
            ):
                self.left_click_state = "dragging"
                gestures.append("left_down")


        # =========================
        # Right click
        # =========================

        if self.right_click_state == "ready":

            if self.right_start_y is None:

                self.right_start_y = current_middle_y


            if (
                current_middle_y
                - self.right_start_y
                >= CLICK_DOWN_DISTANCE
            ):

                self.right_click_state = "down"

                self.right_lowest_y = current_middle_y


        elif self.right_click_state == "down":

            if (
                self.right_lowest_y is None
                or current_middle_y > self.right_lowest_y
            ):

                self.right_lowest_y = current_middle_y


            if (
                self.right_lowest_y
                - current_middle_y
                >= CLICK_UP_DISTANCE
            ):

                gestures.append("right_click")

                self.right_click_state = "ready"

                self.right_start_y = None
                self.right_lowest_y = None


    # =========================
    # Swipe detection
    # =========================

    def detect_swipes(self, world_hand, gestures):
        bend = measure_finger_tilt(world_hand)
        action = self.swipe_detector.update(bend)

        # Temporary diagnostics for camera calibration.
        now = time.monotonic()
        if (
            bend is not None
            and now - getattr(self, "_swipe_debug_at", 0) >= 0.3
        ):
            self._swipe_debug_at = now
            print(
                f"Swipe bend={bend:.1f} "
                f"state={self.swipe_detector.state}",
                flush=True,
            )

        if action is not None:
            direction = SWIPE_DIRECTIONS[action]
            gestures.append(f"swipe_{direction}")
            print(f"Swipe: {action} → {direction}", flush=True)

    # =========================
    # Reset clicking
    # =========================

    def reset_clicks(self):

        self.left_click_state = "ready"
        self.right_click_state = "ready"

        self.left_start_y = None
        self.right_start_y = None

        self.left_lowest_y = None
        self.right_lowest_y = None

        self.left_down_since = None


    # =========================
    # Reset swiping
    # =========================

    def reset_swipe(self):
        self.swipe_detector.reset()