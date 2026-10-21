"""支持绘制危险区域的视频控件。

作者：LiJun
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .config import NormalizedRect


class VideoWidget(QWidget):
    danger_zone_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(720, 480)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._image = QImage()
        self._zone = NormalizedRect()
        self._drag_start: QPointF | None = None
        self._drag_end: QPointF | None = None

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def set_danger_zone(self, zone: NormalizedRect) -> None:
        self._zone = zone.validate()
        self.update()

    def _image_rect(self) -> QRectF:
        if self._image.isNull():
            return QRectF()
        image_size = self._image.size()
        scaled = image_size.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        left = (self.width() - scaled.width()) / 2.0
        top = (self.height() - scaled.height()) / 2.0
        return QRectF(left, top, scaled.width(), scaled.height())

    def _to_normalized(self, point: QPointF) -> QPointF:
        rect = self._image_rect()
        if rect.isEmpty():
            return QPointF(0.0, 0.0)
        x = min(max((point.x() - rect.left()) / rect.width(), 0.0), 1.0)
        y = min(max((point.y() - rect.top()) / rect.height(), 0.0), 1.0)
        return QPointF(x, y)

    def paintEvent(self, event: object) -> None:
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101318"))
        image_rect = self._image_rect()
        if not self._image.isNull():
            painter.drawImage(image_rect, self._image)

        zone = self._zone
        zone_rect = QRectF(
            image_rect.left() + zone.x * image_rect.width(),
            image_rect.top() + zone.y * image_rect.height(),
            zone.width * image_rect.width(),
            zone.height * image_rect.height(),
        )
        painter.fillRect(zone_rect, QColor(255, 188, 56, 35))
        painter.setPen(QPen(QColor("#ffbc38"), 3, Qt.PenStyle.DashLine))
        painter.drawRect(zone_rect)
        painter.setPen(QColor("#ffdc8a"))
        painter.drawText(zone_rect.adjusted(8, 8, -8, -8), "危险区域")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._image_rect().contains(event.position()):
            self._drag_start = self._to_normalized(event.position())
            self._drag_end = self._drag_start

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        self._drag_end = self._to_normalized(event.position())
        self._update_drag_zone(emit=False)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            return
        self._drag_end = self._to_normalized(event.position())
        self._update_drag_zone(emit=True)
        self._drag_start = None
        self._drag_end = None

    def _update_drag_zone(self, *, emit: bool) -> None:
        if self._drag_start is None or self._drag_end is None:
            return
        left = min(self._drag_start.x(), self._drag_end.x())
        top = min(self._drag_start.y(), self._drag_end.y())
        right = max(self._drag_start.x(), self._drag_end.x())
        bottom = max(self._drag_start.y(), self._drag_end.y())
        if right - left < 0.01 or bottom - top < 0.01:
            return
        self._zone = NormalizedRect(left, top, right - left, bottom - top).validate()
        self.update()
        if emit:
            self.danger_zone_changed.emit(self._zone)
