import sys

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView


app = QApplication(sys.argv)

window = QWebEngineView()
window.setWindowTitle("uni.co — Planner")
window.resize(1100, 750)

window.load(QUrl("http://localhost:5173/planner.io/"))
window.loadFinished.connect(
    lambda success: print("Planner loaded:", success)
)

window.show()

sys.exit(app.exec())