import time

from datetime import datetime, time as datetime_time, timedelta
from zoneinfo import ZoneInfo

import cv2

from PySide6.QtCore import QTimer, Qt, Slot, QRectF, QEvent
from PySide6.QtGui import (
    QImage,
    QPixmap,
    QKeySequence,
    QShortcut,
    QColor,
    QPainter,
    QPen,
    QCursor
)
from PySide6.QtWidgets import QMainWindow, QLabel, QApplication

from PySide6.QtWidgets import QPushButton
from ui.settings_panel import SettingsPanel

from ui.panel_style import draw_panel_corners

from vision_worker import VisionWorker
from ui.hud_overlay import HUDOverlay
from scroll_detector import TwoFingerScroll
from finger_tilt import measure_finger_tilt
from ui.assistant_indicator import AssistantIndicator
from ai_assistant.voice_worker import VoiceWorker
from ai_assistant.planner_reader import PlannerReader
from ai_assistant.clap_listener import ClapListener

class MainWindow(QMainWindow):
    def __init__(self, model_path, gestures, mouse):
        super().__init__()

        self.gestures = gestures
        self.mouse = mouse

        self.scroll_detector = TwoFingerScroll()
        self._closing = False
        self._tracking_paused = False
        self._worker_error = None
        self.planner_reader = None
        self.planner_schedule = None

        self._voice_waiting_for_token = False
        
        self.setWindowTitle("uni.co — Camera")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.setFixedSize(448, 348)

        self.camera_label = QLabel(self)
        self.camera_label.setFixedSize(400, 300)
        self.camera_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.camera_label.setText("Starting camera...")
        self.center_camera()

        self.camera_label.setStyleSheet(
            "background: #101019; color: #ddd5ff; border: none;"
        )

        self.hud = HUDOverlay()
        self.assistant_indicator = AssistantIndicator(self)

        bridge = self.hud.desktop_bridge

        bridge.planner_token_ready.connect(
            self.on_planner_token_ready
        )
        bridge.planner_token_failed.connect(
            self.on_planner_token_failed
        )

        self.planner_test_shortcut = self.make_shortcut(
            "Ctrl+Alt+E",
            bridge.request_planner_token,
        )

        area = self.screen().availableGeometry()
        margin = 20

        # Camera starts at the top-right of the usable desktop.
        self.move(
            area.x() + area.width() - self.width() - margin,
            area.y() + margin,
        )

        # Assistant starts at the bottom-left.
        self.assistant_indicator.move(
            area.x() + margin,
            area.y() + area.height()
            - self.assistant_indicator.height() - margin,
        )

        self.assistant_indicator.show()
        self.assistant_indicator.raise_()

        self._voice_failed = False

        self.voice_worker = VoiceWorker(self)
        self.voice_worker.state_changed.connect(
            self.on_voice_state_changed
        )
        self.voice_worker.transcript_ready.connect(
            self.on_voice_transcript
        )
        self.voice_worker.answer_ready.connect(
            self.on_voice_answer
        )
        self.voice_worker.failed.connect(
            self.on_voice_failed
        )
        self.voice_worker.finished.connect(
            self.on_voice_finished
        )

        self.voice_shortcut = self.make_shortcut(
            "Ctrl+Alt+A",
            self.start_voice_turn,
        )
        app = QApplication.instance()
        app.applicationStateChanged.connect(
             self.on_application_state_changed
        )

        self._camera_model_path = model_path
        self._camera_enabled = True
        self.worker = VisionWorker(model_path, self)
        self.worker.failed.connect(self.on_vision_failed)
        self.worker.finished.connect(self.on_worker_finished)

        self.cursor_shortcut = self.make_shortcut(
            "Ctrl+Alt+M", self.select_cursor
        )
        self.hud_shortcut = self.make_shortcut(
            "Ctrl+Alt+J", self.toggle_hud
        )
        self.pause_shortcut = self.make_shortcut(
            "Ctrl+Alt+P", self.toggle_tracking
        )
        self.quit_shortcut = self.make_shortcut(
            "Ctrl+Alt+Q",
            self.close
        )
        self.perf_started = time.perf_counter()
        self.perf_frames = 0
        self.last_result_at = time.monotonic()

        # This timer only checks for finished results.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_frame)
        self.timer.timeout.connect(self.animate_scroll)

        self.worker.start()
        self.timer.start(16)
        self.settings_panel = SettingsPanel()
        self.settings_panel.camera_changed.connect(
            self.set_camera_enabled
        )
        self.settings_panel.talk_requested.connect(
            self.start_voice_turn
        )
        self.settings_panel.planner_requested.connect(
            self.toggle_hud
        )
        self.settings_panel.connection_check_requested.connect(
            self.planner_test_shortcut.activated.emit
        )

        self.settings_panel.voice_changed.connect(
            self.set_voice_mode
        )
        self.settings_panel.voice.setToolTip(
            "Turn the camera off before selecting local speech."
        )

        self.settings_button = QPushButton("⚙")
        self.settings_button.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.settings_button.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.settings_button.setAttribute(
            Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow
        )
        self.settings_button.setAttribute(
            Qt.WidgetAttribute.WA_QuitOnClose, False
        )
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.setToolTip("Settings")
        self.settings_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #8ADFFF;
                font-size: 24px;
            }
            QPushButton:hover {
                color: white;
            }
        """)

        area = self.screen().availableGeometry()
        self.settings_button.move(
            area.x() + area.width() - 60,
            area.y() + area.height() - 60,
        )
        self.settings_button.clicked.connect(self.toggle_settings)
        self.settings_button.show()

        self._clap_enabled = True
        self._voice_requested = False
        self._clap_ready_at = time.monotonic() + 1

        self.clap_listener = ClapListener(self)
        self.clap_listener.failed.connect(self.on_clap_failed)
        self.clap_listener.finished.connect(self.on_clap_finished)

        self.clap_timer = QTimer(self)
        self.clap_timer.timeout.connect(self.ensure_clap_listener)
        self.clap_timer.start(250)

        self.voice_worker.setting_requested.connect(
            self.apply_voice_setting
        )

    def make_shortcut(self, keys, callback):
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(
            Qt.ShortcutContext.ApplicationShortcut
        )
        shortcut.activated.connect(callback)
        return shortcut

    def center_camera(self):
        self.camera_label.move(
            (self.width() - self.camera_label.width()) // 2,
            (self.height() - self.camera_label.height()) // 2
        )

    def reset_input(self):
        self.mouse.move_with_hand(None)
        self.gestures.reset_clicks()
        self.gestures.reset_swipe()
        self.scroll_detector.reset()

    def select_cursor(self):
        if self._tracking_paused or not self.worker.isRunning():
            return

        self.reset_input()
        self.worker.request_cursor_selection()

    def process_frame(self):
        if self._tracking_paused or self._closing:
            return

        result = self.worker.take_latest()
        now = time.monotonic()

        if result is None:
            if now - self.last_result_at > 0.30:
                self.reset_input()
            return

        self.last_result_at = result["completed_at"]

        # Don't act on a result left over from a UI stall.
        if now - self.last_result_at > 0.30:
            self.reset_input()
            return

        frame = result["frame"]
        height, width, _ = frame.shape
        right_hand = result["right_hand"]
        left_hand = result["left_hand"]

        tilt = measure_finger_tilt(
            result.get("right_hand_world")
        )

        scroll_mode, scroll_steps = (
            self.scroll_detector.update(right_hand, tilt)
        )

        if scroll_mode:
            self.mouse.move_with_hand(None)
            self.gestures.reset_clicks()
            self.gestures.reset_swipe()
        else:
            self.mouse.move_with_hand(right_hand)

            for gesture in self.gestures.detect(
                right_hand,
                left_hand,
                swipe_world=result.get("swipe_hand_world"),
            ):
                self.handle_gesture(gesture)

        for hand, label, color in (
            (right_hand, "CURSOR", (0, 255, 255)),
            (left_hand, "SWIPE", (0, 255, 0)),
        ):
            if hand is None:
                continue

            x = int(hand[9].x * width)
            y = int(hand[9].y * height)

            cv2.circle(frame, (x, y), 5, color, -1)
            if label == "CURSOR" and scroll_mode:
                label = "SCROLL"
            cv2.putText(
                frame,
                label,
                (max(0, x - 25), max(15, y - 12)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA
            )

        message = (
            "Finger tilt: unavailable"
            if tilt is None
            else f"Finger tilt: {tilt:+.0f} deg"
        )

        cv2.putText(
            frame,
            message,
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (220, 190, 255),
            1,
            cv2.LINE_AA
        )

        image = QImage(
            frame.data,
            width,
            height,
            frame.strides[0],
            QImage.Format.Format_BGR888
        )

        pixmap = QPixmap.fromImage(image).scaled(
            self.camera_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self.camera_label.setPixmap(pixmap)

        self.perf_frames += 1
        report_time = time.perf_counter()
        elapsed = report_time - self.perf_started

        if elapsed >= 1.0:
            fps = self.perf_frames / elapsed

            self.setWindowTitle(
                f"{fps:.1f} tracking results/s | "
                f"Camera: {result['capture_ms']:.1f} ms | "
                f"Tracking: {result['tracking_ms']:.1f} ms"
            )

            self.perf_started = report_time
            self.perf_frames = 0

    def handle_gesture(self, gesture):
        if gesture in ("left_click", "left_down", "right_click"):
            self.hud.deselect_if_outside(QCursor.pos())

        if gesture == "left_click":
            self.mouse.left_click()
        elif gesture == "left_down":
            self.mouse.left_down()
        elif gesture == "left_up":
            self.mouse.left_up()
        elif gesture == "right_click":
            self.mouse.right_click()
        elif gesture == "swipe_left":
            self.hud.swipe("left")
        elif gesture == "swipe_right":
            self.hud.swipe("right")

    def toggle_hud(self):
        if self.hud.isVisible():
            self.hud.hide()
        else:
            self.hud.restore_panel()
            self.hud.raise_()
            self.hud.activateWindow()

    def toggle_tracking(self):
        self.set_camera_enabled(not self._camera_enabled)

    @Slot(str)
    def on_vision_failed(self, message):
        self._worker_error = message
        self._camera_enabled = False
        self._tracking_paused = True
        self.reset_input()
        self.camera_label.setText(message)

        checkbox = self.settings_panel.camera
        previous = checkbox.blockSignals(True)
        checkbox.setChecked(False)
        checkbox.blockSignals(previous)

        print("Vision error:", message)

    @Slot()
    def on_worker_finished(self):
        self.timer.stop()
        self.reset_input()

        if self._closing:
            self.close()
        elif self._camera_enabled:
            self._start_camera()

    def closeEvent(self, event):
        self._closing = True
        self.settings_panel.hide()
        self.settings_button.hide()
        self.assistant_indicator.hide()
        self.timer.stop()
        self.reset_input()
        self.hud.restore_tab.hide()
        self.hud.hide()

        waiting = False

        self.clap_timer.stop()

        if self.clap_listener.isRunning():
            self.clap_listener.requestInterruption()
            waiting = True

        if self.worker.isRunning():
            self.worker.requestInterruption()
            waiting = True

        if self.voice_worker.isRunning():
            self.voice_worker.requestInterruption()
            waiting = True
        if (
            self.planner_reader is not None
            and self.planner_reader.isRunning()
        ):
            self.planner_reader.requestInterruption()
            waiting = True

        if waiting:
            event.ignore()
            return

        self.mouse.stop()
        self.hud.close()
        event.accept()
    
    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_panel_corners(painter, self.camera_label.geometry())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()

            if handle is not None:
                handle.startSystemMove()
        else:
            super().mousePressEvent(event)
    
    def animate_scroll(self):
        if (
            self._closing
            or self._tracking_paused
            or time.monotonic() - self.last_result_at > 0.30
        ):
            self.scroll_detector.stop_scroll()
            return

        self.mouse.scroll(self.scroll_detector.tick())

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.hud.deselect_if_outside(
                event.globalPosition().toPoint()
            )

        # Let the clicked control continue handling the event.
        return super().eventFilter(watched, event)

    def on_application_state_changed(self, state):
        if state == Qt.ApplicationState.ApplicationInactive:
            self.hud.deselect()
    def start_voice_turn(self):
        if (
            self._closing
            or self.voice_worker.isRunning()
            or self._voice_waiting_for_token
            or self.planner_reader is not None
        ):
            return

        # Button, shortcut, and claps all share this handoff.
        if self.clap_listener.isRunning():
            self._voice_requested = True
            self.clap_listener.requestInterruption()
            return

        self._clap_ready_at = time.monotonic() + 1

        self._voice_failed = False
        self._voice_waiting_for_token = True
        self.assistant_indicator.set_state("thinking")

        print("Connecting planner before listening...", flush=True)
        self.hud.desktop_bridge.request_planner_token()
    def toggle_settings(self):
        panel = self.settings_panel

        if panel.isVisible():
            panel.hide()
        else:
            panel.place_above(self.settings_button)
            panel.show()
            panel.raise_()
            panel.activateWindow()

    def set_camera_enabled(self, enabled):
        if self._closing:
            return

        if enabled and self.voice_worker.voice_mode == "local":
            checkbox = self.settings_panel.camera
            previous = checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(previous)
            checkbox.setToolTip(
                "Select System voice before enabling the camera."
            )
            print(
                "Select System voice before enabling the camera.",
                flush=True,
            )
            return
        
        self._camera_enabled = bool(enabled)
        self._tracking_paused = not self._camera_enabled
        self.reset_input()

        checkbox = self.settings_panel.camera
        previous = checkbox.blockSignals(True)
        checkbox.setChecked(self._camera_enabled)
        checkbox.blockSignals(previous)

        if not self._camera_enabled:
            self.timer.stop()
            self.camera_label.clear()
            self.camera_label.setText("Camera off")

            if self.worker.isRunning():
                self.worker.requestInterruption()
            return

        if self.worker.isRunning():
            # If it is stopping, on_worker_finished will restart it.
            return

        self._start_camera()

    def ensure_clap_listener(self):
        if (
            self._closing
            or not self._clap_enabled
            or self._voice_requested
            or self._voice_waiting_for_token
            or self.voice_worker.isRunning()
            or self.planner_reader is not None
            or self.clap_listener.isRunning()
            or time.monotonic() < self._clap_ready_at
        ):
            return

        self.clap_listener.start()

    def on_clap_failed(self, message):
        self._clap_enabled = False
        print("Clap activation disabled:", message, flush=True)

    def on_clap_finished(self):
        if self._closing:
            self.close()
            return

        requested = (
            self._voice_requested or self.clap_listener.detected
        )
        self._voice_requested = False

        if requested:
            self.start_voice_turn()

    def _start_camera(self):
        if self._closing or not self._camera_enabled:
            return

        old_worker = self.worker

        self._worker_error = None
        self._tracking_paused = False
        self.camera_label.setText("Starting camera...")

        self.worker = VisionWorker(self._camera_model_path, self)
        self.worker.failed.connect(self.on_vision_failed)
        self.worker.finished.connect(self.on_worker_finished)

        old_worker.deleteLater()

        self.perf_started = time.perf_counter()
        self.perf_frames = 0
        self.last_result_at = time.monotonic()

        self.worker.start()
        self.timer.start(16)

    def set_voice_mode(self, mode, *, from_voice=False):
        previous_mode = self.voice_worker.voice_mode

        busy = (
            self.voice_worker.isRunning()
            or self._voice_waiting_for_token
            or self._voice_requested
        )

        camera_busy = (
            self._camera_enabled or self.worker.isRunning()
        )

        if busy and not from_voice:
            message = "Wait until the current voice turn finishes."
        elif mode == "local" and camera_busy:
            message = "Turn off the camera and wait for it to stop."
        elif mode not in ("system", "local"):
            message = "Unknown voice output."
        else:
            self.voice_worker.voice_mode = mode
            message = (
                "Local neural voice selected."
                if mode == "local"
                else "System voice selected."
            )

        selector = self.settings_panel.voice
        previous = selector.blockSignals(True)
        selector.setCurrentIndex(
            selector.findData(self.voice_worker.voice_mode)
        )
        selector.blockSignals(previous)
        selector.setToolTip(message)

        print(message, flush=True)

    @Slot(str)
    def on_voice_state_changed(self, state):
        if not self._closing:
            self.assistant_indicator.set_state(state)

    @Slot(str)
    def on_voice_transcript(self, text):
        print(f"You: {text}", flush=True)

    @Slot(str)
    def on_voice_answer(self, text):
        print(f"uni.co: {text}", flush=True)

    @Slot(str)
    def on_voice_failed(self, message):
        self._voice_failed = True
        print(f"Voice error: {message}", flush=True)

        if not self._closing:
            self.assistant_indicator.set_state("error")

    @Slot()
    def on_voice_finished(self):
        self._clap_ready_at = time.monotonic() + 1
        if self._closing:
            self.close()
        elif not self._voice_failed:
            self.assistant_indicator.set_state("idle")
    
    @Slot(str)
    def on_planner_token_ready(self, token):
        if self._closing:
            self._voice_waiting_for_token = False
            return

        if self._voice_waiting_for_token:
            self._voice_waiting_for_token = False
            self.voice_worker.planner_token = token
            self.voice_worker.start()
            return

        if self.planner_reader is not None:
            return

        self.planner_reader = PlannerReader(token, self)

        self.planner_reader.events_ready.connect(
            self.on_planner_events_ready
        )
        self.planner_reader.failed.connect(
            self.on_planner_token_failed
        )
        self.planner_reader.finished.connect(
            self.on_planner_read_finished
        )

        print("Reading planner events...", flush=True)
        self.planner_reader.start()

    @Slot(object)
    def on_planner_events_ready(self, schedule):
        if self._closing:
            return

        self.planner_schedule = schedule
        timezone = ZoneInfo(schedule["timezone"])

        print(
            f"Backend returned {len(schedule['events'])} "
            f"occurrences for {schedule['start']}.",
            flush=True,
        )

        for event in schedule["events"]:
            start = datetime.fromisoformat(
                event["start"].replace("Z", "+00:00")
            ).astimezone(timezone)

            label = (
                "All day"
                if event.get("allDay")
                else start.strftime("%b %d, %I:%M %p")
            )

            print(
                f"{label} — {event.get('name') or '[Unnamed]'}",
                flush=True,
            )

    @Slot()
    def on_planner_read_finished(self):
        reader = self.planner_reader
        self.planner_reader = None

        if reader is not None:
            reader.deleteLater()

        if self._closing:
            self.close()

    @Slot(str)
    def on_planner_token_failed(self, message):
        print(f"Planner connection: {message}", flush=True)

        if self._voice_waiting_for_token:
            self._voice_waiting_for_token = False

            if not self._closing:
                self.on_voice_failed(
                    "Could not connect to your planner. "
                    "Check that you are signed in."
                )

    @Slot(object)
    def apply_voice_setting(self, request):
        setting, value, future = request

        # A request that timed out before execution must not apply later.
        if not future.set_running_or_notify_cancel():
            return

        try:
            if self._closing:
                result = {"status": "unavailable"}
            elif setting == "planner" and value in (
                "show", "hide", "toggle"
            ):
                # Normalize any in-progress hide first.
                if self.hud._pending_hide is not None:
                    self.hud.slide_animation.stop()
                    self.hud.finish_slide()

                visible = self.hud.isVisible()
                should_show = (
                    not visible if value == "toggle"
                    else value == "show"
                )

                if should_show:
                    if not visible:
                        self.hud.restore_panel()

                    self.hud.raise_()
                    self.hud.activateWindow()
                else:
                    self.hud.hide()
                    self.hud.restore_tab.hide()

                result = {
                    "status": "applied",
                    "panel": "planner",
                    "visible": self.hud.isVisible(),
                }
            elif setting == "camera" and value in ("on", "off"):
                enabled = value == "on"
                self.set_camera_enabled(enabled)

                if self._camera_enabled != enabled:
                    result = {
                        "status": "blocked",
                        "message": (
                            "Select system voice before enabling "
                            "the camera."
                        ),
                    }
                else:
                    result = {
                        "status": "applied",
                        "setting": "camera",
                        "value": value,
                        "message": (
                            "Camera startup requested."
                            if enabled
                            else (
                                "Tracking disabled. Camera resources "
                                "are being released."
                            )
                        ),
                    }

            elif (
                setting == "voice_output"
                and value in ("system", "local")
            ):
                self.set_voice_mode(value, from_voice=True)

                result = {
                    "status": (
                        "applied"
                        if self.voice_worker.voice_mode == value
                        else "blocked"
                    ),
                    "setting": "voice_output",
                    "value": self.voice_worker.voice_mode,
                    "message": self.settings_panel.voice.toolTip(),
                }

            else:
                result = {
                    "status": "invalid",
                    "message": "Unsupported setting or value.",
                }

            future.set_result(result)

        except Exception as error:
            future.set_exception(error)