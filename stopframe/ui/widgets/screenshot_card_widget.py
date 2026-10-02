"""One card in the Screenshots review grid: composited thumbnail, an
auto/manual badge, an exclude button, and a selection border."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from stopframe.core.models import FrameCandidate, FrameOrigin

CARD_WIDTH = 200
THUMB_HEIGHT = 112
CLOSE_ICON_PATH = Path(__file__).resolve().parent.parent / "icons" / "close.svg"


def _repolish(widget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ScreenshotCardWidget(QFrame):
    clicked = Signal(str, object)  # candidate.id, Qt.KeyboardModifiers
    double_clicked = Signal(str)
    exclude_requested = Signal(str)

    def __init__(self, candidate: FrameCandidate, parent=None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.setObjectName("screenshotCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Кадр: {Path(candidate.video_path).name}, {candidate.timestamp_seconds:.1f} секунд")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.image_label = QLabel("Загрузка…")
        self.image_label.setObjectName("cardThumb")
        self.image_label.setFixedSize(CARD_WIDTH - 8, THUMB_HEIGHT)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        is_auto = candidate.origin == FrameOrigin.AUTO
        self.badge = QLabel("АВТО" if is_auto else "ВРУЧНУЮ")
        self.badge.setObjectName("badgeAuto" if is_auto else "badgeManual")

        self.exclude_button = QPushButton()
        self.exclude_button.setObjectName("iconButton")
        self.exclude_button.setIcon(QIcon(str(CLOSE_ICON_PATH)))
        self.exclude_button.setIconSize(QSize(14, 14))
        self.exclude_button.setFixedSize(24, 24)
        self.exclude_button.setToolTip("Убрать кадр из экспорта")
        self.exclude_button.setAccessibleName("Убрать кадр из экспорта")
        self.exclude_button.clicked.connect(lambda: self.exclude_requested.emit(self.candidate.id))

        top_row = QHBoxLayout()
        top_row.addWidget(self.badge)
        top_row.addStretch(1)
        top_row.addWidget(self.exclude_button)

        self.caption = QLabel(f"{Path(candidate.video_path).name}  ·  {candidate.timestamp_seconds:.1f}s")
        self.caption.setProperty("class", "caption")
        self.caption.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(8)
        layout.addLayout(top_row)
        layout.addWidget(self.image_label)
        layout.addWidget(self.caption)

        self.set_selected(False)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")
        self.image_label.setProperty("state", "normal")
        _repolish(self.image_label)

    def set_error(self, message: str) -> None:
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(message)
        self.image_label.setProperty("state", "error")
        _repolish(self.image_label)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        _repolish(self)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.clicked.emit(self.candidate.id, event.modifiers())
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.double_clicked.emit(self.candidate.id)
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.candidate.id, event.modifiers())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.double_clicked.emit(self.candidate.id)
        super().mouseDoubleClickEvent(event)
