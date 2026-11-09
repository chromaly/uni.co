import math
import time

import cv2
import mediapipe as mp


# Distances are measured relative to image height.
MAX_HAND_STEP = 0.25
AMBIGUITY_MARGIN = 0.08
MAX_TRACKING_GAP = 0.30


class HandTracker:
    def __init__(self, model_path):
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=model_path
            ),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2
        )

        self.landmarker = (
            mp.tasks.vision.HandLandmarker.create_from_options(
                options
            )
        )

        self.cursor_position = None
        self.cursor_last_seen = None
        self.selection_requested = False

        self.pinch_started = None
        self.pinch_last_seen = None
    def request_cursor_selection(self):
        self.cursor_position = None
        self.cursor_last_seen = None
        self.selection_requested = True
        print("Cursor selection requested. Show only your right hand.")

    def clear_cursor(self):
        if self.cursor_position is not None:
            print("Cursor tracking lost. Hold a pinch to activate again.")

        self.cursor_position = None
        self.cursor_last_seen = None

        self.pinch_started = None
        self.pinch_last_seen = None

    @staticmethod
    def palm_position(hand):
        # Average several palm landmarks for a steadier reference.
        indices = (0, 5, 9, 13, 17)

        return (
            sum(hand[i].x for i in indices) / len(indices),
            sum(hand[i].y for i in indices) / len(indices)
        )

    def process_frame(self, frame, timestamp_ms):
        self.cursor_world = None
        self.swipe_world = None
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        result = self.landmarker.detect_for_video(
            image,
            timestamp_ms
        )

        hands = result.hand_landmarks
        now = time.monotonic()

        if self.selection_requested:
            self.selection_requested = False

            if len(hands) != 1:
                print("Selection failed: show exactly one hand, then retry.")
                return None, None

            self.cursor_position = self.palm_position(hands[0])
            self.cursor_last_seen = now

            print("Cursor hand selected.")
            return hands[0], None

        # Activate cursor control with a deliberate pinch hold.
        if self.cursor_position is None:
            if len(hands) != 1:
                self.pinch_started = None
                self.pinch_last_seen = None
                return None, None

            hand = hands[0]
            aspect = frame.shape[1] / frame.shape[0]

            def distance(a, b):
                return math.hypot(
                    (hand[a].x - hand[b].x) * aspect,
                    hand[a].y - hand[b].y
                )

            # Compare fingertip distance with palm width so the
            # threshold scales with distance from the camera.
            palm_width = distance(5, 17)
            pinched = (
                palm_width > 0.001
                and distance(4, 8) / palm_width < 0.30
            )

            gap = (
                self.pinch_last_seen is None
                or now - self.pinch_last_seen > MAX_TRACKING_GAP
            )

            if not pinched:
                self.pinch_started = None
                self.pinch_last_seen = None
                return None, None

            if self.pinch_started is None or gap:
                self.pinch_started = now

            self.pinch_last_seen = now

            if now - self.pinch_started >= 0.5:
                self.cursor_position = self.palm_position(hand)
                self.cursor_last_seen = now
                self.pinch_started = None
                self.pinch_last_seen = None

                print("Cursor activated.")

            # Start passing cursor input on the following frame.
            return None, None

        if (
            not hands
            or now - self.cursor_last_seen > MAX_TRACKING_GAP
        ):
            self.clear_cursor()
            return None, None

        aspect = frame.shape[1] / frame.shape[0]
        previous_x, previous_y = self.cursor_position

        candidates = []

        for index, hand in enumerate(hands):
            x, y = self.palm_position(hand)

            distance = math.hypot(
                (x - previous_x) * aspect,
                y - previous_y
            )

            candidates.append((distance, index))

        candidates.sort()
        closest_distance, cursor_index = candidates[0]

        too_far = closest_distance > MAX_HAND_STEP

        ambiguous = (
            len(candidates) > 1
            and candidates[1][0] - closest_distance
            < AMBIGUITY_MARGIN
        )

        if too_far or ambiguous:
            self.clear_cursor()
            return None, None

        cursor_hand = hands[cursor_index]

        self.cursor_position = self.palm_position(cursor_hand)
        self.cursor_last_seen = now

        # With two detected hands, the other one gets swipe control.
        swipe_index = next(
            (
                index
                for index in range(len(hands))
                if index != cursor_index
            ),
            None,
        )

        swipe_hand = (
            hands[swipe_index]
            if swipe_index is not None
            else None
        )

        world_hands = result.hand_world_landmarks

        if cursor_index < len(world_hands):
            self.cursor_world = world_hands[cursor_index]

        if (
            swipe_index is not None
            and swipe_index < len(world_hands)
        ):
            self.swipe_world = world_hands[swipe_index]

        return cursor_hand, swipe_hand