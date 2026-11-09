import math
import time

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget


class AssistantIndicator(QWidget):
    LABELS = {
        "idle": "uni.co",
        "listening": "Listening…",
        "transcribing": "Understanding…",
        "thinking": "Thinking…",
        "speaking": "Speaking…",
        "error": "Something went wrong",
    }

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint,
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow
        )

        self.setWindowTitle("uni.co — Assistant")
        self.setFixedSize(190, 220)

        self.state = "idle"
        self.level = 0.0
        self._drag_offset = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)

    def set_state(self, state):
        if state not in self.LABELS:
            raise ValueError(f"Unknown assistant state: {state}")

        self.state = state
        self.update()

    def set_level(self, level):
        self.level = max(0.0, min(1.0, float(level)))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        now = time.monotonic()
        cx = self.width() / 2
        cy = self.height() / 2 - 12

        active = self.state != "idle"
        speaking = self.state == "speaking"
        processing = self.state in ("thinking", "transcribing")

        accent = QColor(
            "#FFB627" if self.state == "error" else "#8ADFFF"
        )

        # Stay small and quiet when idle.
        radius = 58 if not active else 64
        pulse = 0.5 + 0.5 * math.sin(now * 3)
        radius += pulse * (1.5 if active else 0.4)

        # A delicate circular outline, with speech-like movement.
        ring = QPainterPath()

        for step in range(181):
            angle = step / 180 * math.tau
            ripple = 0.0

            if speaking:
                ripple = (
                    math.sin(angle * 5 + now * 4)
                    + 0.5 * math.sin(angle * 8 - now * 3)
                ) * (1.0 + self.level * 2.5)

            r = radius + ripple
            x = cx + math.cos(angle) * r
            y = cy + math.sin(angle) * r

            if step == 0:
                ring.moveTo(x, y)
            else:
                ring.lineTo(x, y)

        ring.closeSubpath()

        # Faint edge light only during interaction.
        if active:
            for width, alpha in ((7, 10), (4, 22)):
                color = QColor(accent)
                color.setAlpha(alpha)
                painter.setPen(QPen(color, width))
                painter.drawPath(ring)

        color = QColor(accent)
        color.setAlpha(210 if active else 85)
        painter.setPen(QPen(color, 1.2))
        painter.drawPath(ring)

        # Three separated arcs outside the main ring.
        outer = radius + 9
        bounds = QRectF(
            cx - outer, cy - outer,
            outer * 2, outer * 2,
        )

        rotation = (now * 28) % 360 if processing else 0

        for index, start in enumerate((12, 142, 262)):
            color = QColor(accent)
            color.setAlpha(
                (180, 110, 65)[index] if active else 45
            )

            pen = QPen(color, 1.6)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(
                bounds,
                round((start + rotation) * 16),
                64 * 16,
            )

        # No permanent name or caption beneath the idle ring.
        if active:
            painter.setPen(QColor("#B9D5DF"))
            painter.drawText(
                QRectF(0, cy + 88, self.width(), 24),
                Qt.AlignmentFlag.AlignCenter,
                self.LABELS[self.state],
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._drag_offset is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(
                event.globalPosition().toPoint()
                - self._drag_offset
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)