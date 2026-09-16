"""Double-click detail view: a bigger, zoomable preview plus per-frame logo
nudge controls, so a single problem frame can be fixed without touching the
slot's overall default."""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import Settings
from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate
from stopframe.ui.widgets.zoomable_graphics_view import ZoomableGraphicsView

SCALE_SLIDER_FACTOR = 100  # slider is int-only; scale 0.05..5.00 -> 5..500


class _ResettableSlider(QSlider):
    """Double-click snaps the slider back to its default value — offset 0
    or scale 1.0, i.e. the overlay exactly as designed."""

    def __init__(self, default_value: int, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.default_value = default_value

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.setValue(self.default_value)


class FrameDetailDialog(QDialog):
    def __init__(self, candidate: FrameCandidate, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.settings = settings
        self.setWindowTitle(f"{Path(candidate.video_path).name} — {candidate.timestamp_seconds:.1f}s")
        self.resize(760, 560)

        self.preview_view = ZoomableGraphicsView()
        self.preview_view.setObjectName("previewSurface")
        self.preview_view.setMinimumSize(480, 270)
        self.preview_scene = QGraphicsScene(self)
        self.preview_view.setScene(self.preview_scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.preview_scene.addItem(self.pixmap_item)
        self.error_text_item = self.preview_scene.addText("Could not read frame")
        self.error_text_item.setDefaultTextColor(QColor("#5a5a60"))
        self.error_text_item.setVisible(False)

        zoom_hint = QLabel("Scroll or pinch to zoom, double-click to reset")
        zoom_hint.setProperty("class", "caption")
        reset_zoom_button = QPushButton("Reset Zoom")
        reset_zoom_button.clicked.connect(self.preview_view.reset_zoom)
        preview_toolbar = QHBoxLayout()
        preview_toolbar.addWidget(zoom_hint)
        preview_toolbar.addStretch(1)
        preview_toolbar.addWidget(reset_zoom_button)

        placement = candidate.logo_placement

        self.offset_x_slider, self.offset_x_value = self._make_slider(-2000, 4000, placement.offset_x, default=0)
        self.offset_y_slider, self.offset_y_value = self._make_slider(-2000, 4000, placement.offset_y, default=0)
        self.scale_slider, self.scale_value = self._make_slider(
            5, 500, round(placement.scale * SCALE_SLIDER_FACTOR), default=SCALE_SLIDER_FACTOR
        )

        self.offset_x_slider.valueChanged.connect(self._on_changed)
        self.offset_y_slider.valueChanged.connect(self._on_changed)
        self.scale_slider.valueChanged.connect(self._on_changed)

        controls = QVBoxLayout()
        controls.setSpacing(6)
        controls.addWidget(self._slider_row("Offset X", self.offset_x_slider, self.offset_x_value))
        controls.addWidget(self._slider_row("Offset Y", self.offset_y_slider, self.offset_y_value))
        controls.addWidget(self._slider_row("Scale", self.scale_slider, self.scale_value))

        close_button = QPushButton("Done")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(preview_toolbar)
        layout.addWidget(self.preview_view, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(close_button)

        self._update_value_labels()
        self._render()

    @staticmethod
    def _make_slider(minimum: int, maximum: int, value: int, default: int) -> tuple[QSlider, QLabel]:
        slider = _ResettableSlider(default)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setValue(value)
        value_label = QLabel()
        value_label.setFixedWidth(40)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return slider, value_label

    @staticmethod
    def _slider_row(name: str, slider: QSlider, value_label: QLabel) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(name)
        label.setFixedWidth(60)
        row_layout.addWidget(label)
        row_layout.addWidget(slider, stretch=1)
        row_layout.addWidget(value_label)
        return row

    def _update_value_labels(self) -> None:
        self.offset_x_value.setText(str(self.offset_x_slider.value()))
        self.offset_y_value.setText(str(self.offset_y_slider.value()))
        self.scale_value.setText(f"{self.scale_slider.value() / SCALE_SLIDER_FACTOR:.2f}")

    def _on_changed(self) -> None:
        self.candidate.logo_placement.offset_x = self.offset_x_slider.value()
        self.candidate.logo_placement.offset_y = self.offset_y_slider.value()
        self.candidate.logo_placement.scale = self.scale_slider.value() / SCALE_SLIDER_FACTOR
        self._update_value_labels()
        self._render()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.preview_view.fit_to_window(self.pixmap_item.boundingRect())

    def _render(self) -> None:
        source = FrameSource(self.candidate.video_path)
        frame = source.read_at(self.candidate.timestamp_seconds)
        source.close()
        if frame is None:
            self.pixmap_item.setPixmap(QPixmap())
            self.error_text_item.setVisible(True)
            return

        if self.candidate.hdr_fix:
            frame = apply_hdr_fix(frame)

        image = frame_to_image(frame)
        slot = self.settings.logo_slots.get(self.candidate.logo_placement.slot_key)
        logo_path = slot.path if slot else None
        composed = compose_logo(image, logo_path, self.candidate.logo_placement)

        pixmap = QPixmap.fromImage(ImageQt(composed))
        self.error_text_item.setVisible(False)
        self.pixmap_item.setPixmap(pixmap)
        self.preview_scene.setSceneRect(self.pixmap_item.boundingRect())
