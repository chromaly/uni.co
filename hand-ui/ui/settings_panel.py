from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
)

from PySide6.QtGui import QColor, QPainter
from ui.panel_style import draw_panel_corners

class SettingsPanel(QWidget):
    camera_changed = Signal(bool)
    voice_changed = Signal(str)
    talk_requested = Signal()
    planner_requested = Signal()
    connection_check_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_QuitOnClose, False
        )
        self.setWindowTitle("Settings")
        self.setFixedWidth(370)

        self.setStyleSheet("""
            QWidget {
                background: transparent;
                color: #DCEAF0;
                font-family: Menlo;
                font-size: 12px;
                border: none;
            }
            QLabel#heading {
                color: #8ADFFF;
                font-size: 14px;
            }
            QPushButton {
                text-align: left;
                padding: 8px 4px;
                border-bottom: 1px solid #294550;
            }
            QPushButton:hover {
                color: #8ADFFF;
                background: rgba(138, 223, 255, 15);
            }
            QComboBox {
                background: #10212B;
                padding: 6px;
                color: #8ADFFF;
            }
            QComboBox QAbstractItemView {
                background: #081218;
                color: #DCEAF0;
                selection-background-color: #234552;
            }
            QCheckBox {
                spacing: 10px;
                padding: 8px 0;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
                border: 1px solid #8ADFFF;
                background: transparent;
            }
            QCheckBox::indicator:checked {
                background: #8ADFFF;
            }
        """)
        self.setObjectName("settings")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 34, 36, 36)
        layout.setSpacing(14)

        header = QHBoxLayout()
        heading = QLabel("SETTINGS")
        heading.setObjectName("heading")
        close_button = QPushButton("×")
        close_button.setFixedWidth(32)
        close_button.clicked.connect(self.hide)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(close_button)
        layout.addLayout(header)

        self.camera = QCheckBox("Camera & gestures")
        self.camera.setChecked(True)
        self.camera.toggled.connect(self.camera_changed.emit)
        layout.addWidget(self.camera)

        voice_row = QHBoxLayout()
        voice_row.addWidget(QLabel("Voice output"))
        self.voice = QComboBox()
        self.voice.addItem("System", "system")
        self.voice.addItem("Local neural", "local")
        self.voice.currentIndexChanged.connect(
            lambda _: self.voice_changed.emit(
                self.voice.currentData()
            )
        )
        voice_row.addWidget(self.voice)
        layout.addLayout(voice_row)

        for text, signal in (
            ("Talk · Ctrl+Option+A", self.talk_requested),
            ("Show / hide Planner · Ctrl+Option+J",
             self.planner_requested),
            ("Check Planner connection",
             self.connection_check_requested),
        ):
            button = QPushButton(text)
            button.clicked.connect(
                lambda checked=False, action=signal: action.emit()
            )
            layout.addWidget(button)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        surface = self.rect().adjusted(20, 20, -20, -20)
        painter.fillRect(surface, QColor("#081218"))

        draw_panel_corners(
            painter,
            surface,
            selected=self.isActiveWindow(),
        )
        
    def place_above(self, button):
        self.adjustSize()
        area = button.screen().availableGeometry()
        self.move(
            area.x() + area.width() - self.width() - 20,
            button.y() - self.height() - 10,
        )