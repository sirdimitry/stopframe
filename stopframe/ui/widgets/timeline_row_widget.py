"""One row in the Timeline tab: file name label + its filmstrip.

Clicking the label activates the row (makes it the preview source)
without moving its playhead; clicking/dragging the filmstrip activates
the row too and moves the playhead.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from stopframe.core.models import VideoItem
from stopframe.ui.widgets.filmstrip_widget import FilmstripWidget

LABEL_WIDTH = 170


class _ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class TimelineRowWidget(QWidget):
    activated = Signal()
    position_changed = Signal(float)

    def __init__(self, video: VideoItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video = video

        elided = QFontMetrics(self.font()).elidedText(video.file_name, Qt.TextElideMode.ElideMiddle, LABEL_WIDTH)
        self.label = _ClickableLabel(elided)
        self.label.setFixedWidth(LABEL_WIDTH)
        self.label.setToolTip(video.file_name)
        self.label.clicked.connect(self.activated.emit)

        self.filmstrip = FilmstripWidget()
        self.filmstrip.set_duration(video.duration_seconds)
        self.filmstrip.setMinimumWidth(200)
        self.filmstrip.position_changed.connect(self._on_filmstrip_position_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self.label)
        layout.addWidget(self.filmstrip, stretch=1)

        self.set_active(False)

    def _on_filmstrip_position_changed(self, fraction: float) -> None:
        self.activated.emit()
        self.position_changed.emit(fraction)

    def set_active(self, active: bool) -> None:
        border = "2px solid palette(highlight)" if active else "1px solid transparent"
        self.setStyleSheet(f"TimelineRowWidget {{ border: {border}; }}")
