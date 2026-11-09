from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen

def draw_panel_corners(painter, geometry, selected=False):
    rect = QRectF(geometry).adjusted(-3, -3, 3, 3)
    length = 22

    def draw_strokes():
        for x, y, dx, dy in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):
            corner = QPointF(x, y)
            painter.drawLine(
                corner, QPointF(x + dx * length, y)
            )
            painter.drawLine(
                corner, QPointF(x, y + dy * length)
            )

    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    if selected:
        # Wide, faint outlines create a halo around the whole panel.
        for width, opacity in (
            (28, 3),
            (22, 5),
            (16, 8),
            (10, 14),
            (5, 22),
        ):
            color = QColor("#8ADFFF")
            color.setAlpha(opacity)
            painter.setPen(QPen(color, width))
            painter.drawRoundedRect(rect, 3, 3)

    painter.setPen(QPen(QColor("#8ADFFF"), 1.5))
    draw_strokes()
    painter.restore()