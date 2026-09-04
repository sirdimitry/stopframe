"""A scrubbable strip of thumbnails spanning a video's full length, with a
draggable playhead and colored markers for already-captured frames.

Thumbnails are drawn stretched to fill the widget's current width, so it
resizes cleanly without needing to regenerate them.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import QWidget

from stopframe.core.models import FrameCandidate, FrameOrigin

STRIP_HEIGHT = 64
MARKER_HEIGHT = 6
STRIP_BACKGROUND = QColor(0x1b, 0x1b, 0x1e)
PLAYHEAD_COLOR = QColor(255, 60, 60)
AUTO_MARKER_COLOR = QColor(90, 160, 255)
# Kept clearly outside the accent-orange family (#ff6a1f) used everywhere
# else for actions/selection, so a manual-capture marker never reads as
# "this is clickable" — a warm yellow instead of the near-orange it was.
MANUAL_MARKER_COLOR = QColor(255, 214, 90)
LOADING_TEXT_COLOR = QColor(157, 156, 163)
ERROR_TEXT_COLOR = QColor(255, 128, 128)


def _bgr_ndarray_to_pixmap(frame: np.ndarray) -> QPixmap:
    height, width = frame.shape[:2]
    rgb = np.ascontiguousarray(frame[:, :, ::-1])
    image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class FilmstripWidget(QWidget):
    position_changed = Signal(float)  # fraction 0..1, user-driven (click/drag)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(STRIP_HEIGHT + MARKER_HEIGHT)
        self.setFixedHeight(STRIP_HEIGHT + MARKER_HEIGHT)
        self._thumbnails: list[QPixmap] = []
        self._markers: list[FrameCandidate] = []
        self._duration_seconds = 0.0
        self.position_fraction = 0.0
        self._dragging = False
        self._load_attempted = False

    def set_thumbnails(self, thumbnails: list[np.ndarray]) -> None:
        self._load_attempted = True
        self._thumbnails = [_bgr_ndarray_to_pixmap(t) for t in thumbnails]
        self.update()

    def set_markers(self, markers: list[FrameCandidate]) -> None:
        self._markers = markers
        self.update()

    def set_position(self, fraction: float) -> None:
        self.position_fraction = min(1.0, max(0.0, fraction))
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), STRIP_BACKGROUND)

        if self._thumbnails:
            segment_width = self.width() / len(self._thumbnails)
            for index, pixmap in enumerate(self._thumbnails):
                target = QRectF(index * segment_width, 0, segment_width + 1, STRIP_HEIGHT)
                painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        elif self._load_attempted:
            painter.setPen(ERROR_TEXT_COLOR)
            painter.drawText(
                self.rect().adjusted(0, 0, 0, -MARKER_HEIGHT), Qt.AlignmentFlag.AlignCenter, "Could not read video"
            )
        else:
            painter.setPen(LOADING_TEXT_COLOR)
            painter.drawText(self.rect().adjusted(0, 0, 0, -MARKER_HEIGHT), Qt.AlignmentFlag.AlignCenter, "Loading…")

        for marker in self._markers:
            if self._duration_seconds <= 0:
                continue
            fraction = min(1.0, max(0.0, marker.timestamp_seconds / self._duration_seconds))
            x = fraction * self.width()
            color = MANUAL_MARKER_COLOR if marker.origin == FrameOrigin.MANUAL else AUTO_MARKER_COLOR
            painter.fillRect(QRectF(x - 2, STRIP_HEIGHT, 4, MARKER_HEIGHT), color)

        x = self.position_fraction * self.width()
        painter.setPen(PLAYHEAD_COLOR)
        painter.drawLine(int(x), 0, int(x), self.height())

    def set_duration(self, duration_seconds: float) -> None:
        self._duration_seconds = duration_seconds

    def _fraction_at(self, event: QMouseEvent) -> float:
        return min(1.0, max(0.0, event.position().x() / max(1, self.width())))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            fraction = self._fraction_at(event)
            self.set_position(fraction)
            self.position_changed.emit(fraction)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            fraction = self._fraction_at(event)
            self.set_position(fraction)
            self.position_changed.emit(fraction)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update()
