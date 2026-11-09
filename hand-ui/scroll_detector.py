import math
import time


NEUTRAL_BEND = 45
DEADZONE = 10

ENTER_TIME = 0.20
EXIT_TIME = 0.30
RELEASE_DELAY = 0.20

ANGLE_SMOOTHING_TIME = 0.08
MAX_SCROLL_SPEED = 12 

STROKE_WINDOW = 0.18
REARM_TIME = 0.15

MIN_FLICK_SPEED = 6
MAX_FLICK_SPEED = 40
MOMENTUM_TIME = 0.45


class TwoFingerScroll:
    def __init__(self):
        self.reset()

    def reset(self):
        self._active = False
        self._enter_since = None
        self._exit_since = None
        self._release_until = 0.0
        self._last_time = None
        self._smooth_bend = None
        self._remainder = 0.0
        self.velocity = 0.0
        self._stroke = None
        self._wait_for_neutral = False
        self._neutral_since = None
        self._last_tick = time.monotonic()

    @staticmethod
    def distance(hand, a, b):
        return math.hypot(
            (hand[a].x - hand[b].x) * (4 / 3),
            hand[a].y - hand[b].y
        )

    def finger_extended(self, hand, tip, joint):
        return (
            self.distance(hand, 0, tip)
            > self.distance(hand, 0, joint) * 1.15
        )

    def stop_scroll(self):
        self.velocity = 0.0
        self._remainder = 0.0
        self._smooth_bend = None
        self._stroke = None
        self._wait_for_neutral = True
        self._neutral_since = None

    def update(self, hand, bend):
        now = time.monotonic()

        if hand is None:
            self.reset()
            return False, 0

        if (
            self._last_time is not None
            and now - self._last_time > 0.30
        ):
            self.reset()

        dt = (
            0.0 if self._last_time is None
            else min(now - self._last_time, 0.10)
        )
        self._last_time = now

        if now < self._release_until:
            return True, 0

        if bend is None or not math.isfinite(bend):
            self.stop_scroll()
            self._enter_since = None
            self._exit_since = None
            return self._active, 0

        index = self.finger_extended(hand, 8, 6)
        middle = self.finger_extended(hand, 12, 10)
        ring = self.finger_extended(hand, 16, 14)
        pinky = self.finger_extended(hand, 20, 18)

        open_palm = index and middle and ring and pinky
        other_fingers_curled = not ring and not pinky
        near_neutral = abs(bend - NEUTRAL_BEND) <= DEADZONE

        # Enter with ring/pinky curled and index/middle
        # resting near the chosen neutral bend.
        if not self._active:
            if other_fingers_curled and near_neutral:
                if self._enter_since is None:
                    self._enter_since = now

                if now - self._enter_since >= ENTER_TIME:
                    self._active = True
                    self._smooth_bend = bend
                    print("Scroll mode entered")

                return True, 0

            if self._enter_since is not None:
                self._enter_since = None
                self._release_until = now + RELEASE_DELAY
                return True, 0

            return False, 0

        # An open palm exits; bending index/middle does not.
        if open_palm:
            self.stop_scroll()

            if self._exit_since is None:
                self._exit_since = now

            if now - self._exit_since >= EXIT_TIME:
                self.reset()
                self._last_time = now
                self._release_until = now + RELEASE_DELAY
                print("Scroll mode exited")

            return True, 0

        self._exit_since = None

        if not other_fingers_curled:
            if self._stroke is not None or abs(self.velocity) >= 0.6:
                print(
                    "Scroll interrupted:",
                    f"ring_extended={ring}",
                    f"pinky_extended={pinky}",
                    flush=True,
                )

            self.stop_scroll()
            return True, 0

        if self._smooth_bend is None:
            self._smooth_bend = bend

        alpha = 1 - math.exp(-dt / ANGLE_SMOOTHING_TIME)
        self._smooth_bend += (
            bend - self._smooth_bend
        ) * alpha

        offset = self._smooth_bend - NEUTRAL_BEND

        near_neutral = abs(offset) <= DEADZONE

        # Returning to neutral only prepares another stroke.
        if self._wait_for_neutral:
                # Use a wider resting range between strokes.
                resting = near_neutral

                if resting:
                    if self._neutral_since is None:
                        self._neutral_since = now

                    if now - self._neutral_since >= REARM_TIME:
                        self._wait_for_neutral = False
                        self._neutral_since = None
                        print("Scroll ready", flush=True)
                else:
                    self._neutral_since = None

                return True, 0

        # Start measuring an outward stroke.
        if self._stroke is None:
            if near_neutral:
                return True, 0

            direction = 1 if offset < 0 else -1
            self._stroke = (now, direction, abs(offset))
            return True, 0

        started, direction, peak = self._stroke

        current_direction = 1 if offset < 0 else -1

        if current_direction == direction:
            peak = max(peak, abs(offset))

        self._stroke = (started, direction, peak)

        # Finish after a short window or an early return to neutral.
        if now - started < STROKE_WINDOW and not near_neutral:
            return True, 0

        usable_range = 12 if direction > 0 else 18
        
        strength = min(
            1.0,
            max(0.0, peak - DEADZONE) / usable_range
        )

        # One launch per stroke. Holding the pose adds nothing.
        self.velocity = direction * (
            MIN_FLICK_SPEED
            + (MAX_FLICK_SPEED - MIN_FLICK_SPEED)
            * strength ** 1.4
        )
        self._remainder = 0.0
        self._last_tick = now
        self._stroke = None
        self._wait_for_neutral = True
        self._neutral_since = now if near_neutral else None

        print("Scroll burst launched", flush=True)
        return True, 0
    
    def tick(self):
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now

        # Avoid a large jump after a stalled interface.
        if dt > 0.15:
            self.stop_scroll()
            return 0

        if abs(self.velocity) < 0.6:
            self.velocity = 0.0
            self._remainder = 0.0
            return 0

        decay = math.exp(-dt / MOMENTUM_TIME)

        # Integrate the distance while velocity decays.
        self._remainder += (
            self.velocity * MOMENTUM_TIME * (1 - decay)
        )
        self.velocity *= decay

        steps = int(self._remainder)
        self._remainder -= steps

        return steps