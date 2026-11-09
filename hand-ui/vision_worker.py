import threading
import time

import cv2
from PySide6.QtCore import QThread, Signal

from hand_tracker import HandTracker


class VisionWorker(QThread):
    failed = Signal(str)

    def __init__(self, model_path, parent=None):
        super().__init__(parent)

        self.model_path = str(model_path)

        self._lock = threading.Lock()
        self._latest = None
        self._paused = False
        self._generation = 0
        self._reset_requested = False
        self._selection_requested = False

    def take_latest(self):
        # The UI takes the newest result, not a backlog of frames.
        with self._lock:
            result = self._latest
            self._latest = None
            return result

    def set_paused(self, paused):
        with self._lock:
            self._paused = paused
            self._generation += 1
            self._latest = None
            self._reset_requested = True
            self._selection_requested = False

    def request_cursor_selection(self):
        with self._lock:
            self._generation += 1
            self._latest = None
            self._selection_requested = True

    def run(self):
        camera = None
        tracker = None

        try:
            # Create and use these resources in the worker thread.
            camera = cv2.VideoCapture(0)
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

            if not camera.isOpened():
                raise RuntimeError("Could not open the camera.")

            tracker = HandTracker(self.model_path)
            start_time = time.monotonic()
            consecutive_failures = 0

            while not self.isInterruptionRequested():
                with self._lock:
                    paused = self._paused
                    generation = self._generation

                    reset = self._reset_requested
                    select = self._selection_requested

                    if not paused:
                        self._reset_requested = False
                        self._selection_requested = False

                if paused:
                    self.msleep(20)
                    continue

                if reset:
                    tracker.clear_cursor()

                if select:
                    tracker.request_cursor_selection()

                capture_start = time.perf_counter()
                success, frame = camera.read()
                capture_ms = (
                    time.perf_counter() - capture_start
                ) * 1000

                if not success or frame is None:
                    consecutive_failures += 1

                    if consecutive_failures >= 10:
                        raise RuntimeError(
                            "Camera failed to return a frame after 10 attempts."
                        )

                    self.msleep(30)
                    continue

                consecutive_failures = 0

                frame = cv2.flip(frame, 1)

                timestamp_ms = int(
                    (time.monotonic() - start_time) * 1000
                )

                tracking_start = time.perf_counter()
                right_hand, left_hand = tracker.process_frame(
                    frame,
                    timestamp_ms
                )
                tracking_ms = (
                    time.perf_counter() - tracking_start
                ) * 1000

                result = {
                    "frame": frame,
                    "right_hand": right_hand,
                    "right_hand_world": tracker.cursor_world,
                    "swipe_hand_world": tracker.swipe_world,
                    "left_hand": left_hand,
                    "capture_ms": capture_ms,
                    "tracking_ms": tracking_ms,
                    "completed_at": time.monotonic(),
                }

                with self._lock:
                    # Discard work completed after a pause or
                    # selection request changed the current state.
                    if (
                        generation == self._generation
                        and not self._paused
                        and not self.isInterruptionRequested()
                    ):
                        self._latest = result

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            if camera is not None:
                camera.release()

            if tracker is not None:
                tracker.landmarker.close()