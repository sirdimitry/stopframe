"""Double-click detail view: a bigger preview plus per-frame logo nudge
controls, so a single problem frame can be fixed without touching the
slot's overall default."""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from stopframe.config import Settings
from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate


class FrameDetailDialog(QDialog):
    def __init__(self, candidate: FrameCandidate, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.settings = settings
        self.setWindowTitle(f"{Path(candidate.video_path).name} — {candidate.timestamp_seconds:.1f}s")
        self.resize(760, 560)

        self.preview_label = QLabel()
        self.preview_label.setObjectName("previewSurface")
        self.preview_label.setMinimumSize(480, 270)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        placement = candidate.logo_placement
        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-2000, 4000)
        self.offset_x_spin.setValue(placement.offset_x)
        self.offset_x_spin.valueChanged.connect(self._on_changed)

        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-2000, 4000)
        self.offset_y_spin.setValue(placement.offset_y)
        self.offset_y_spin.valueChanged.connect(self._on_changed)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.05, 5.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(placement.scale)
        self.scale_spin.valueChanged.connect(self._on_changed)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Offset X"))
        controls.addWidget(self.offset_x_spin)
        controls.addSpacing(12)
        controls.addWidget(QLabel("Offset Y"))
        controls.addWidget(self.offset_y_spin)
        controls.addSpacing(12)
        controls.addWidget(QLabel("Scale"))
        controls.addWidget(self.scale_spin)
        controls.addStretch(1)

        close_button = QPushButton("Done")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self.preview_label, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(close_button)

        self._render()

    def _on_changed(self) -> None:
        self.candidate.logo_placement.offset_x = self.offset_x_spin.value()
        self.candidate.logo_placement.offset_y = self.offset_y_spin.value()
        self.candidate.logo_placement.scale = self.scale_spin.value()
        self._render()

    def _render(self) -> None:
        source = FrameSource(self.candidate.video_path)
        frame = source.read_at(self.candidate.timestamp_seconds)
        source.close()
        if frame is None:
            self.preview_label.setText("Could not read frame")
            return

        if self.candidate.hdr_fix:
            frame = apply_hdr_fix(frame)

        image = frame_to_image(frame)
        slot = self.settings.logo_slots.get(self.candidate.logo_placement.slot_key)
        logo_path = slot.path if slot else None
        composed = compose_logo(image, logo_path, self.candidate.logo_placement)

        pixmap = QPixmap.fromImage(ImageQt(composed))
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)
