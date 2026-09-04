"""One logo slot: Browse + preview + offset X/Y + scale.

Mutates the LogoSlot instance it's given in place and emits `changed`
whenever the user edits anything, so the owner can persist settings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import LogoSlot
from stopframe.logging_setup import get_logger, log_ui_action

logger = get_logger("ui.logo_slot_widget")

PREVIEW_SIZE = 64


class LogoSlotWidget(QGroupBox):
    changed = Signal()

    def __init__(self, slot_key: str, slot: LogoSlot, parent: QWidget | None = None) -> None:
        super().__init__(slot_key, parent)
        self.slot_key = slot_key
        self.slot = slot

        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.preview.setStyleSheet("border: 1px solid palette(mid);")
        self.preview.setScaledContents(False)

        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._on_browse)

        nudge_hint = "Fine-tune only — the overlay already fills the frame as designed."

        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-2000, 4000)
        self.offset_x_spin.setValue(slot.offset_x)
        self.offset_x_spin.setToolTip(nudge_hint)
        self.offset_x_spin.valueChanged.connect(self._on_offset_x_changed)

        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-2000, 4000)
        self.offset_y_spin.setValue(slot.offset_y)
        self.offset_y_spin.setToolTip(nudge_hint)
        self.offset_y_spin.valueChanged.connect(self._on_offset_y_changed)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.05, 5.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(slot.scale)
        self.scale_spin.setToolTip(nudge_hint)
        self.scale_spin.valueChanged.connect(self._on_scale_changed)

        controls = QVBoxLayout()
        controls.addWidget(browse_button)
        controls.addWidget(self._labeled_row("Offset X", self.offset_x_spin))
        controls.addWidget(self._labeled_row("Offset Y", self.offset_y_spin))
        controls.addWidget(self._labeled_row("Scale", self.scale_spin))

        layout = QHBoxLayout(self)
        layout.addWidget(self.preview)
        layout.addLayout(controls, stretch=1)

        self._refresh_preview()

    @staticmethod
    def _labeled_row(text: str, field: QWidget) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(QLabel(text))
        row_layout.addWidget(field, stretch=1)
        return row

    def _refresh_preview(self) -> None:
        if not self.slot.path:
            self.preview.clear()
            return
        pixmap = QPixmap(self.slot.path)
        if pixmap.isNull():
            self.preview.setText("invalid PNG")
            return
        self.preview.setPixmap(
            pixmap.scaled(
                PREVIEW_SIZE,
                PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, f"Choose logo for {self.slot_key}", "", "PNG Images (*.png)")
        if not path:
            return
        self.slot.path = path
        self._refresh_preview()
        log_ui_action(logger, "logo_browse", f"slot={self.slot_key}")
        self.changed.emit()

    def _on_offset_x_changed(self, value: int) -> None:
        self.slot.offset_x = value
        self.changed.emit()

    def _on_offset_y_changed(self, value: int) -> None:
        self.slot.offset_y = value
        self.changed.emit()

    def _on_scale_changed(self, value: float) -> None:
        self.slot.scale = value
        self.changed.emit()
