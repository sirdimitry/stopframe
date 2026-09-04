"""One card in the Screenshots review grid: composited thumbnail, an
auto/manual badge, an exclude button, and a selection border."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from stopframe.core.models import FrameCandidate, FrameOrigin

CARD_WIDTH = 200
THUMB_HEIGHT = 112


class ScreenshotCardWidget(QFrame):
    clicked = Signal(str, object)  # candidate.id, Qt.KeyboardModifiers
    double_clicked = Signal(str)
    exclude_requested = Signal(str)

    def __init__(self, candidate: FrameCandidate, parent=None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.setFixedWidth(CARD_WIDTH)
        self.setFrameShape(QFrame.Shape.Box)

        self.image_label = QLabel("Loading…")
        self.image_label.setFixedSize(CARD_WIDTH - 8, THUMB_HEIGHT)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background:#222; color:#888;")

        is_auto = candidate.origin == FrameOrigin.AUTO
        self.badge = QLabel("AUTO" if is_auto else "MANUAL")
        self.badge.setStyleSheet(
            f"background:{'#5aa0ff' if is_auto else '#ffaa28'}; color:black; "
            "font-weight:bold; font-size:10px; padding:1px 4px;"
        )

        self.exclude_button = QPushButton("✕")
        self.exclude_button.setFixedSize(20, 20)
        self.exclude_button.setToolTip("Exclude from export")
        self.exclude_button.clicked.connect(lambda: self.exclude_requested.emit(self.candidate.id))

        top_row = QHBoxLayout()
        top_row.addWidget(self.badge)
        top_row.addStretch(1)
        top_row.addWidget(self.exclude_button)

        self.caption = QLabel(f"{Path(candidate.video_path).name}  ·  {candidate.timestamp_seconds:.1f}s")
        self.caption.setStyleSheet("font-size:10px; color:palette(mid);")
        self.caption.setWordWrap(True)

        layout = QVBoxLayout(self)
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

    def set_selected(self, selected: bool) -> None:
        color = "palette(highlight)" if selected else "palette(mid)"
        width = 3 if selected else 1
        self.setStyleSheet(f"ScreenshotCardWidget {{ border: {width}px solid {color}; }}")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.candidate.id, event.modifiers())
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.double_clicked.emit(self.candidate.id)
        super().mouseDoubleClickEvent(event)
