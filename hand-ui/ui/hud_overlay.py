from PySide6.QtCore import Qt, QUrl, QRectF, QPoint, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QKeySequence,
    QShortcut,
)


from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView

from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
)

from desktop_bridge import install_desktop_bridge

from ui.panel_style import draw_panel_corners

class PanelGrip(QWidget):
    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def paintEvent(self, event):
        painter = QPainter(self)

        # A painted surface gives this area a reliable hit target.
        color = QColor("#FFB627")
        color.setAlpha(28 if self.panel.selected else 1)
        painter.fillRect(self.rect(), color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panel.begin_drag(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.panel.continue_drag(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.panel._drag_offset = None
            event.accept()

class HUDOverlay(QWidget):
    def __init__(self):
        super().__init__()

        self.selected = False
        self._drag_offset = None

        self._hidden_side = None

        self.slide_animation = QPropertyAnimation(self, b"pos", self)
        self.slide_animation.setDuration(280)
        self.slide_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self._pending_hide = None
        self.slide_animation.finished.connect(
            self.finish_slide
        )

        self.setWindowTitle("uni.co — Planner")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )
        area = self.screen().availableGeometry()

        self.resize(
            min(900, round(area.width() * 0.65)),
            min(620, round(area.height() * 0.75)),
        )

        # Transparent space around the webpage for the glow.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        self.browser = QWebEngineView(self)

        # A named profile stores browser data between launches.
        self.profile = QWebEngineProfile(
            "planner",
            QApplication.instance()
        )

        self.page = QWebEnginePage(
            self.profile,
            self.browser
        )
        self.browser.setPage(self.page)

        self.desktop_channel, self.desktop_bridge = (
            install_desktop_bridge(self.browser)
        )
        self.browser.page().setBackgroundColor(
            QColor(0, 0, 0, 0)
        )
        self.browser.setStyleSheet("background: transparent;")

        self.browser.load(
            QUrl("https://chromaly.github.io/planner.io/?embed=uni")
        )
        layout.addWidget(self.browser)
        self.grips = [PanelGrip(self) for _ in range(4)]

        self._restore_position = None

        self.restore_tab = QPushButton("P")
        self.restore_tab.setAccessibleName("Restore Planner")
        self.restore_tab.setToolTip("Restore Planner")

        self.restore_tab.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )

        self.restore_tab.setAttribute(
            Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow,
            True,
        )
        self.restore_tab.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating,
            True,
        )
        self.restore_tab.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.restore_tab.setFixedSize(48, 108)
        self.style_restore_tab("right")
        self.restore_tab.clicked.connect(self.restore_panel)

        # Hide without a visible close button.
        self.hide_shortcut = QShortcut(
            QKeySequence("Escape"),
            self
        )
        self.hide_shortcut.activated.connect(self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_panel_corners(
            painter,
            self.browser.geometry(),
            selected=self.selected,
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        # Only handle the surrounding area, not webpage content.
        if self.browser.geometry().contains(
            event.position().toPoint()
        ):
            super().mousePressEvent(event)
            return

        self.selected = True
        self._drag_offset = (
            event.globalPosition().toPoint()
            - self.frameGeometry().topLeft()
        )
        self.update()
        event.accept()

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
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            event.accept()
            return

        super().mouseReleaseEvent(event)
    def position_grips(self):
        self.layout().activate()
        box = self.browser.geometry()
        thickness = 16

        rectangles = (
            (box.x(), box.y(), box.width(), thickness),
            (
                box.x(),
                box.y() + box.height() - thickness,
                box.width(),
                thickness,
            ),
            (box.x(), box.y(), thickness, box.height()),
            (
                box.x() + box.width() - thickness,
                box.y(),
                thickness,
                box.height(),
            ),
        )

        for grip, rectangle in zip(self.grips, rectangles):
            grip.setGeometry(*rectangle)
            grip.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "grips"):
            self.position_grips()

    def showEvent(self, event):
        super().showEvent(event)
        self.position_grips()

    def begin_drag(self, global_position):
        self.slide_animation.stop()
        self._pending_hide = None
        self.selected = True
        self._drag_offset = (
            global_position - self.frameGeometry().topLeft()
        )
        self.update()

        for grip in self.grips:
            grip.update()

    def continue_drag(self, global_position):
        if self._drag_offset is not None:
            self.move(global_position - self._drag_offset)
    
    def swipe(self, direction):
        if not self.selected or self._drag_offset is not None:
            return

        if not self.isVisible():
            opposite = {
                "left": "right",
                "right": "left",
            }.get(self._hidden_side)

            if direction == opposite:
                self.restore_panel()

            return
        if (
            self.slide_animation.state()
            == QPropertyAnimation.State.Running
        ):
            return
        screen = (
            QApplication.screenAt(self.frameGeometry().center())
            or self.screen()
        )
        area = screen.availableGeometry()

        left = area.x()
        right = area.x() + area.width() - self.width()

        # Oversized panels stay aligned with the chosen edge.
        target_x = left if direction == "left" else right
        max_y = area.y() + max(0, area.height() - self.height())
        target_y = max(area.y(), min(self.y(), max_y))

        already_at_edge = abs(self.x() - target_x) <= 4

        if not already_at_edge:
            self.slide_animation.setStartValue(self.pos())
            self.slide_animation.setEndValue(
                QPoint(target_x, target_y)
            )
            self.slide_animation.start()
            return

        self._restore_position = self.pos()

        self.style_restore_tab(direction)

        tab_x = (
            area.x()
            if direction == "left"
            else area.x() + area.width() - self.restore_tab.width()
        )
        tab_y = max(
            area.y(),
            min(
                target_y,
                area.y() + area.height() - self.restore_tab.height(),
            ),
        )

        # Move beyond the display, then hide to avoid appearing
        # on an adjacent monitor.
        offscreen_x = (
            area.x() - self.width()
            if direction == "left"
            else area.x() + area.width()
        )
        self._pending_hide = (
            direction,
            QPoint(tab_x, tab_y),
        )

        self.slide_animation.setStartValue(self.pos())
        self.slide_animation.setEndValue(
            QPoint(offscreen_x, target_y)
        )
        self.slide_animation.start()

    def restore_panel(self):
        animate_restore = (
            not self.isVisible()
            and self._hidden_side is not None
            and self._restore_position is not None
        )

        self.slide_animation.stop()
        self._pending_hide = None
        self.restore_tab.hide()

        # Hiding left the panel positioned beyond the screen edge.
        start_position = self.pos()

        self._hidden_side = None

        if not animate_restore:
            self.show()
            self.raise_()
            return

        self.show()
        self.raise_()

        self.slide_animation.setStartValue(start_position)
        self.slide_animation.setEndValue(
            self._restore_position
        )
        self.slide_animation.start()

    def style_restore_tab(self, side):
        # Round only the edge facing into the desktop.
        if side == "left":
            corners = """
                border-top-right-radius: 16px;
                border-bottom-right-radius: 16px;
            """
            accent_edge = "border-right: 3px solid #7B5EDB;"
        else:
            corners = """
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
            """
            accent_edge = "border-left: 3px solid #7B5EDB;"

        self.restore_tab.setStyleSheet(f"""
            QPushButton {{
                background: rgba(33, 27, 48, 235);
                color: #DCD2FF;
                border: none;
                font-size: 20px;
                font-weight: 500;
                {corners}
                {accent_edge}
            }}
            QPushButton:hover {{
                background: rgba(65, 48, 94, 245);
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background: #55418A;
            }}
        """)
    def finish_slide(self):
        if self._pending_hide is None:
            return

        direction, tab_position = self._pending_hide
        self._pending_hide = None

        self._hidden_side = direction
        self.hide()

        self.restore_tab.move(tab_position)
        self.restore_tab.show()
        self.restore_tab.raise_()

    def hideEvent(self, event):
        self.slide_animation.stop()
        self._pending_hide = None
        super().hideEvent(event)
    
    def deselect(self):
        # Keep tucked-away panels selected for swipe-to-restore.
        if not self.isVisible() or self._pending_hide is not None:
            return

        self.selected = False
        self._drag_offset = None
        self.update()

        for grip in self.grips:
            grip.update()

    def deselect_if_outside(self, global_position):
        if not self.frameGeometry().contains(global_position):
            self.deselect()