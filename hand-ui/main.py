from pathlib import Path

from PySide6.QtWidgets import QApplication

from gestures import GestureDetector
from mouse_controller import MouseController
from ui.main_window import MainWindow


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "webcam-shennanigans"
    / "hand_landmarker.task"
)


def main():
    app = QApplication([])

    app.setOrganizationName("Chromaly")
    app.setApplicationName("uni.co")
    
    gestures = GestureDetector()
    mouse = MouseController()

    window = MainWindow(MODEL_PATH, gestures, mouse)
    window.show()

    app.exec()


if __name__ == "__main__":
    main()