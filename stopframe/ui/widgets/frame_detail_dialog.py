"""Zoomable frame review with navigation, HDR, rotation and logo controls.
Edits update the shared candidates immediately; only the current decoded
frame is retained while moving through the review order."""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QButtonGroup,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import Settings, build_slot_key, parse_slot_key
from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate, LogoPlacement
from stopframe.core.rotation import rotate_frame
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
    candidate_changed = Signal(object)

    def __init__(self, candidate: FrameCandidate, settings: Settings, parent=None,
                 candidates: list[FrameCandidate] | None = None) -> None:
        super().__init__(parent)
        self.candidate = candidate
        self.settings = settings
        self.candidates = [c for c in (candidates or [candidate]) if c.included]
        if not any(c.id == candidate.id for c in self.candidates):
            self.candidates.insert(0, candidate)
        self._index = next(i for i, c in enumerate(self.candidates) if c.id == candidate.id)
        self._frame = None
        self.setWindowTitle(f"{Path(candidate.video_path).name} — {candidate.timestamp_seconds:.1f}s")
        self.resize(960, 720)

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

        zoom_hint = QLabel("Колесо или жест — масштаб · двойной щелчок — сброс")
        zoom_hint.setProperty("class", "caption")
        reset_zoom_button = QPushButton("Сбросить масштаб")
        reset_zoom_button.clicked.connect(self.preview_view.reset_zoom)
        preview_toolbar = QHBoxLayout()
        preview_toolbar.addWidget(zoom_hint)
        preview_toolbar.addStretch(1)
        preview_toolbar.addWidget(reset_zoom_button)

        self.previous_button = QPushButton("← Предыдущий")
        self.next_button = QPushButton("Следующий →")
        self.previous_button.setToolTip("Предыдущий кадр · Alt+←")
        self.next_button.setToolTip("Следующий кадр · Alt+→")
        self.previous_button.clicked.connect(lambda: self._navigate(-1))
        self.next_button.clicked.connect(lambda: self._navigate(1))
        self.position_label = QLabel()
        self.position_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.position_label.setWordWrap(True)
        navigation = QHBoxLayout()
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.position_label, stretch=1)
        navigation.addWidget(self.next_button)
        self._navigation_shortcuts = []
        for key, step in (("Alt+Left", -1), ("Alt+Right", 1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda step=step: self._navigate(step))
            self._navigation_shortcuts.append(shortcut)

        self.hdr_button = QPushButton("Коррекция HDR")
        self.hdr_button.setCheckable(True)
        self.hdr_button.clicked.connect(self._toggle_hdr)
        self.rotate_button = QPushButton("↻ Повернуть на 90°")
        self.rotate_button.clicked.connect(self._rotate)
        self.left_button = QPushButton("Слева")
        self.right_button = QPushButton("Справа")
        self.side_buttons = QButtonGroup(self)
        for button, side in ((self.left_button, "left"), (self.right_button, "right")):
            button.setCheckable(True)
            self.side_buttons.addButton(button)
            button.clicked.connect(lambda checked=False, side=side: self._set_side(side))
        editing = QHBoxLayout()
        editing.addWidget(self.hdr_button)
        editing.addWidget(self.rotate_button)
        editing.addStretch(1)
        editing.addWidget(QLabel("Логотип:"))
        editing.addWidget(self.left_button)
        editing.addWidget(self.right_button)

        for button in (self.previous_button, self.next_button, self.hdr_button,
                       self.rotate_button, self.left_button, self.right_button, reset_zoom_button):
            button.setAutoDefault(False)

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
        controls.addWidget(self._slider_row("Сдвиг X", self.offset_x_slider, self.offset_x_value))
        controls.addWidget(self._slider_row("Сдвиг Y", self.offset_y_slider, self.offset_y_value))
        controls.addWidget(self._slider_row("Масштаб", self.scale_slider, self.scale_value))

        close_button = QPushButton("Готово")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(navigation)
        layout.addLayout(editing)
        layout.addLayout(preview_toolbar)
        layout.addWidget(self.preview_view, stretch=1)
        layout.addLayout(controls)
        layout.addWidget(close_button)

        self._load_candidate()

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
        label.setFixedWidth(80)
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
        self.candidate_changed.emit(self.candidate)

    def _sync_controls(self) -> None:
        placement = self.candidate.logo_placement
        for slider, value in ((self.offset_x_slider, placement.offset_x),
                              (self.offset_y_slider, placement.offset_y),
                              (self.scale_slider, round(placement.scale * SCALE_SLIDER_FACTOR))):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self.hdr_button.setChecked(self.candidate.hdr_fix)
        self.hdr_button.setText("HDR: включено" if self.candidate.hdr_fix else "Коррекция HDR")
        _, _, side = parse_slot_key(placement.slot_key)
        self.left_button.setChecked(side == "left")
        self.right_button.setChecked(side == "right")
        self._update_value_labels()

    def _load_candidate(self) -> None:
        self.setWindowTitle(f"{Path(self.candidate.video_path).name} — {self.candidate.timestamp_seconds:.1f}s")
        self.position_label.setText(f"{self._index + 1} / {len(self.candidates)}  ·  "
                                    f"{Path(self.candidate.video_path).name}  ·  {self.candidate.timestamp_seconds:.1f} с")
        self.previous_button.setEnabled(self._index > 0)
        self.next_button.setEnabled(self._index < len(self.candidates) - 1)
        source = FrameSource(self.candidate.video_path)
        try:
            self._frame = source.read_at(self.candidate.timestamp_seconds)
        finally:
            source.close()
        self._sync_controls()
        self._render()
        self.preview_view.reset_zoom()

    def _navigate(self, step: int) -> None:
        index = self._index + step
        if 0 <= index < len(self.candidates):
            self._index = index
            self.candidate = self.candidates[index]
            self._load_candidate()

    def _edited(self, reset_zoom: bool = False) -> None:
        self._sync_controls()
        self._render()
        if reset_zoom:
            self.preview_view.reset_zoom()
        self.candidate_changed.emit(self.candidate)

    def _toggle_hdr(self, checked: bool) -> None:
        self.candidate.hdr_fix = checked
        self._edited()

    def _rotate(self) -> None:
        self.candidate.rotation_quarter_turns = (self.candidate.rotation_quarter_turns + 1) % 4
        aspect, orientation, side = parse_slot_key(self.candidate.logo_placement.slot_key)
        orientation = "portrait" if orientation == "landscape" else "landscape"
        self.candidate.logo_placement.slot_key = build_slot_key(aspect, orientation, side)
        self._edited(reset_zoom=True)

    def _set_side(self, side: str) -> None:
        aspect, orientation, _ = parse_slot_key(self.candidate.logo_placement.slot_key)
        key = build_slot_key(aspect, orientation, side)
        if key != self.candidate.logo_placement.slot_key and key in self.settings.logo_slots:
            slot = self.settings.logo_slots[key]
            self.candidate.logo_placement = LogoPlacement(key, slot.offset_x, slot.offset_y, slot.scale)
        self._edited()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.preview_view.fit_to_window(self.pixmap_item.boundingRect())

    def _render(self) -> None:
        frame = self._frame
        if frame is None:
            self.pixmap_item.setPixmap(QPixmap())
            self.error_text_item.setVisible(True)
            return

        frame = rotate_frame(frame, self.candidate.rotation_quarter_turns)
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
