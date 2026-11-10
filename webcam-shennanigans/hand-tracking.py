import os

os.environ["MEDIAPIPE_DISABLE_GPU"] = "1"

import sys
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap

import cv2
import mediapipe as mp
import pyautogui
import time


MODEL_PATH = "hand_landmarker.task"

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False



# MediaPipe setup


BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode

options = HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=RunningMode.VIDEO,
    num_hands=2
)



# Screen and mouse settings


screen_width, screen_height = pyautogui.size()

active_left = 0.20
active_right = 0.80
active_top = 0.15
active_bottom = 0.70

desired_interval = 1 / 60


# Clicking settings


CLICK_DOWN_DISTANCE = 0.04
CLICK_UP_DISTANCE = 0.02

# Swiping settings

SWIPE_DISTANCE = 0.20
SWIPE_TIME = 0.5

class CameraWindow(QMainWindow):

    def __init__(self, landmarker):

        super().__init__()

        # -------------------------
        # Window
        # -------------------------

        self.setWindowTitle("Hand Tracking")

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.resize(480, 360)


        # -------------------------
        # MediaPipe
        # -------------------------

        self.landmarker = landmarker


        # -------------------------
        # Camera display
        # -------------------------

        self.camera_label = QLabel()

        self.camera_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setCentralWidget(self.camera_label)


        # -------------------------
        # Camera
        # -------------------------

        self.cap = cv2.VideoCapture(0)

        self.cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            640
        )

        self.cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            480
        )

        if not self.cap.isOpened():

            print("Could not open camera")
            sys.exit()


        # -------------------------
        # Timing
        # -------------------------

        self.start_time = time.monotonic()

        self.last_mouse_update = 0


        # -------------------------
        # Clicking state
        # -------------------------

        self.left_click_state = "ready"
        self.right_click_state = "ready"

        self.left_start_y = None
        self.right_start_y = None

        self.left_lowest_y = None
        self.right_lowest_y = None

        # Swiping state

        self.swipe_start_x = None
        self.swipe_start_time = None
        # -------------------------
        # Camera timer
        # -------------------------

        self.timer = QTimer()

        self.timer.timeout.connect(
            self.update_frame
        )

        self.timer.start(16)

        # SMOOTHING MOVEMENT

        self.smooth_x = None
        self.smooth_y = None

        self.deadzone = 0.003
        self.smoothing = 0.35


    def update_frame(self):

        
        # Read camera frame
        

        success, frame = self.cap.read()

        if not success:

            print("Could not read frame")
            return


        # Mirror camera

        frame = cv2.flip(frame, 1)


        
        # MediaPipe
        

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame_rgb
        )


        frame_timestamp_ms = int(
            (time.monotonic() - self.start_time) * 1000
        )


        result = self.landmarker.detect_for_video(
            mp_image,
            frame_timestamp_ms
        )


        current_time = time.monotonic()


        
        # Hand tracking
        

        if result.hand_landmarks:
            
            # defining hands
            right_hand = None
            left_hand = None
            for i, landmarks in enumerate(result.hand_landmarks):
                handedness = result.handedness[i][0].category_name

                if handedness == "Left":
                    right_hand = landmarks
                elif handedness == "Right":
                    left_hand = landmarks
            

            # right handed logic: controlling movement and clicking

            if right_hand is not None:

                center_palm = right_hand[9]

                index_finger = right_hand[8]

                middle_finger = right_hand[12]


                
                # CLICKING LOGIC
                

                current_index_y = (
                    index_finger.y
                    - center_palm.y
                )

                current_middle_y = (
                    middle_finger.y
                    - center_palm.y
                )


                
                # LEFT CLICK
                

                
                if self.left_click_state == "ready":

                    if self.left_start_y is None:

                        self.left_start_y = current_index_y

                    if (
                        current_index_y
                        - self.left_start_y
                        >= CLICK_DOWN_DISTANCE
                    ):

                        self.left_click_state = "down"

                        self.left_lowest_y = current_index_y


                elif self.left_click_state == "down":

                    # Keep track of the lowest point
                    # the finger reaches.

                    if (
                        self.left_lowest_y is None
                        or current_index_y > self.left_lowest_y
                    ):

                        self.left_lowest_y = current_index_y


                    # Detect upward movement from
                    # the lowest point.

                    if (
                        self.left_lowest_y
                        - current_index_y
                        >= CLICK_UP_DISTANCE
                    ):

                        pyautogui.click()

                        print("clicked!")

                        self.left_click_state = "ready"

                        self.left_start_y = None

                        self.left_lowest_y = None


                
                # RIGHT CLICK
                

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

                    # Keep track of the lowest point
                    # the finger reaches.

                    if (
                        self.right_lowest_y is None
                        or current_middle_y > self.right_lowest_y
                    ):

                        self.right_lowest_y = current_middle_y


                    # Detect upward movement from
                    # the lowest point.

                    if (
                        self.right_lowest_y
                        - current_middle_y
                        >= CLICK_UP_DISTANCE
                    ):

                        pyautogui.rightClick()

                        print("right clicked!")

                        self.right_click_state = "ready"

                        self.right_start_y = None

                        self.right_lowest_y = None


                
                # Mouse movement
                

                if (
                    current_time
                    - self.last_mouse_update
                    >= desired_interval
                ):

                    normalized_x = (center_palm.x - active_left) / (active_right - active_left)
                    normalized_y = (center_palm.y - active_top) / (active_bottom - active_top)

                    normalized_x = max(0, min(1, normalized_x))
                    normalized_y = max(0, min(1, normalized_y))

                    if self.smooth_x is None:
                        self.smooth_x = normalized_x
                        self.smooth_y = normalized_y
                    else:
                        dx = normalized_x - self.smooth_x
                        dy = normalized_y - self.smooth_y

                        # Ignore tiny movements caused by hand jitter
                        if abs(dx) > self.deadzone:
                            self.smooth_x += dx * self.smoothing

                        if abs(dy) > self.deadzone:
                            self.smooth_y += dy * self.smoothing

                    pyautogui.moveTo(
                        self.smooth_x * screen_width,
                        self.smooth_y * screen_height,
                        duration=0
                    )


                    self.last_mouse_update = current_time
            else:
                # Hand disappeared.
                # Reset unfinished gestures.

                self.left_click_state = "ready"
                self.right_click_state = "ready"

                self.left_start_y = None
                self.right_start_y = None

                self.left_lowest_y = None
                self.right_lowest_y = None

            if left_hand is not None:
                palm_center = left_hand[9]

                current_x = palm_center.x
                current_time = time.monotonic()

                if self.swipe_start_time is None:
                    self.swipe_start_x = current_x
                    self.swipe_start_time = current_time

                distance = current_x - self.swipe_start_x
                elapsed = current_time - self.swipe_start_time

                if elapsed <= SWIPE_TIME:
                    if distance <= -SWIPE_DISTANCE:
                        print("SWIPE LEFT")
                        self.swipe_start_x = None
                        self.swipe_start_time = None
                    elif distance >= SWIPE_DISTANCE:
                        print("SWIPE RIGHT")
                        self.swipe_start_x = None
                        self.swipe_start_time = None
                else:
                    self.swipe_start_x = current_x
                    self.swipe_start_time = current_time


        
        # Display camera in PySide6
        

        frame_rgb = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB
        )

        height, width, channels = frame_rgb.shape

        bytes_per_line = channels * width

        image = QImage(
            frame_rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        )


        pixmap = QPixmap.fromImage(image)


        pixmap = pixmap.scaled(
            self.camera_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )


        self.camera_label.setPixmap(pixmap)


    def closeEvent(self, event):

        # Stop timer

        self.timer.stop()

        # Release camera

        self.cap.release()

        event.accept()

with HandLandmarker.create_from_options(options) as landmarker:
    app = QApplication(sys.argv)
    window = CameraWindow(landmarker)
    window.show()
    sys.exit(app.exec())