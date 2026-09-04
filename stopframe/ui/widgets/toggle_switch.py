"""A small sliding on/off switch — left (off) / right (on, orange) — for
the one setting that reads better as a physical switch than a checkbox:
whether export bakes the logo in at all."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

_TRACK_OFF = QColor(0x2a, 0x2a, 0x2e)
_TRACK_ON = QColor(0xff, 0x6a, 0x1f)
_THUMB = QColor(0xf2, 0xf1, 0xee)
_WIDTH = 44
_HEIGHT = 24
_MARGIN = 3


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, checked: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._checked = checked
        self.setFixedSize(_WIDTH, _HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked == checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(checked)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(_TRACK_ON if self._checked else _TRACK_OFF)
        painter.drawRoundedRect(QRectF(0, 0, _WIDTH, _HEIGHT), _HEIGHT / 2, _HEIGHT / 2)

        thumb_diameter = _HEIGHT - 2 * _MARGIN
        x = _WIDTH - thumb_diameter - _MARGIN if self._checked else _MARGIN
        painter.setBrush(_THUMB)
        painter.drawEllipse(QRectF(x, _MARGIN, thumb_diameter, thumb_diameter))
