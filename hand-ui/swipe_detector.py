import math
import time


class SwipeDetector:
    REST_MAX = 15
    START_BEND = 18
    DEEP_BEND = 40

    ARM_TIME = 0.08
    MAX_MOTION_TIME = 2.5
    MAX_TRACKING_GAP = 0.30

    def __init__(self, resting_bend=10):
        self.REST_MAX = resting_bend + 5
        self.START_BEND = resting_bend + 8
        self.DEEP_BEND = resting_bend + 30
        self.reset()

    def reset(self):
        self.state = "rest"
        self.rest_since = None
        self.motion_since = None
        self.peak_bend = None
        self.last_seen = None

    def update(self, bend, now=None):
        """Return 'small_bend', 'deep_bend', or None."""
        if now is None:
            now = time.monotonic()

        if bend is None or not math.isfinite(bend):
            self.reset()
            return None

        if (
            self.last_seen is not None
            and now - self.last_seen > self.MAX_TRACKING_GAP
        ):
            self.reset()

        self.last_seen = now
        resting = bend <= self.REST_MAX

        if self.state == "rest":
            if not resting:
                self.rest_since = None
                return None

            if self.rest_since is None:
                self.rest_since = now

            if now - self.rest_since >= self.ARM_TIME:
                self.state = "armed"

            return None

        if self.state == "armed":
            if bend < self.START_BEND:
                return None

            self.state = "stroke"
            self.motion_since = now
            self.peak_bend = bend
            return None

        # Record the deepest bend throughout the stroke.
        self.peak_bend = max(self.peak_bend, bend)

        if now - self.motion_since > self.MAX_MOTION_TIME:
            print(
                f"Swipe cancelled: return took too long "
                f"(peak={self.peak_bend:.1f})",
                flush=True,
            )
            self.reset()
            return None
        
        if not resting:
            return None

        action = (
            "deep_bend"
            if self.peak_bend >= self.DEEP_BEND
            else "small_bend"
        )

        self.reset()
        return action