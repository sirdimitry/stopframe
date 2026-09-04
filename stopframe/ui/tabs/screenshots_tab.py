"""Tab 3 — Screenshots: the review grid of captured frames.

Cards are grouped by source video. Click selects (replacing the current
selection, or toggling off if it was the only one selected); Cmd/Ctrl-click
adds/removes a single card; Shift-click selects a contiguous range from the
last-clicked card. The Left/Right/4:3/16:9 panel reassigns the logo slot
for every selected card, keeping the video's own orientation. Fix HDR Color
toggles the approximate HLG correction for the selected cards. The ✕ on a
card excludes that frame from export; double-click opens a bigger preview
with per-frame offset/scale controls.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import Settings, build_slot_key, parse_slot_key
from stopframe.core.capture_store import CaptureStore
from stopframe.core.models import FrameCandidate, LogoPlacement
from stopframe.logging_setup import get_logger, log_ui_action
from stopframe.ui.widgets.flow_layout import FlowLayout
from stopframe.ui.widgets.frame_detail_dialog import FrameDetailDialog
from stopframe.ui.widgets.screenshot_card_widget import ScreenshotCardWidget
from stopframe.ui.workers.card_render_worker import CardRenderWorker

logger = get_logger("ui.screenshots_tab")


class ScreenshotsTab(QWidget):
    def __init__(self, capture_store: CaptureStore, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.capture_store = capture_store
        self.settings = settings

        self.cards: dict[str, ScreenshotCardWidget] = {}
        self.selected_ids: set[str] = set()
        self.anchor_id: str | None = None
        self._card_order: list[str] = []
        self._group_containers: dict[str, QWidget] = {}
        self._render_workers: list[CardRenderWorker] = []

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_toolbar())

        self.groups_container = QWidget()
        self.groups_layout = QVBoxLayout(self.groups_container)
        self.groups_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.groups_container)
        layout.addWidget(scroll, stretch=1)

        self.capture_store.frame_added.connect(self._on_frame_added)
        for candidate in self.capture_store.frames:
            self._add_card(candidate)

    # -- Toolbar -------------------------------------------------------

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)

        left_button = QPushButton("Left")
        left_button.clicked.connect(lambda: self._apply_side("left"))
        right_button = QPushButton("Right")
        right_button.clicked.connect(lambda: self._apply_side("right"))
        ratio_43_button = QPushButton("4:3")
        ratio_43_button.clicked.connect(lambda: self._apply_aspect("4:3"))
        ratio_169_button = QPushButton("16:9")
        ratio_169_button.clicked.connect(lambda: self._apply_aspect("16:9"))
        hdr_button = QPushButton("Fix HDR Color")
        hdr_button.clicked.connect(self._toggle_hdr_fix)

        row.addWidget(QLabel("Assign logo:"))
        row.addWidget(left_button)
        row.addWidget(right_button)
        row.addWidget(ratio_43_button)
        row.addWidget(ratio_169_button)
        row.addSpacing(16)
        row.addWidget(hdr_button)
        row.addStretch(1)
        return bar

    # -- Card creation / rendering ---------------------------------------

    def _on_frame_added(self, candidate: FrameCandidate) -> None:
        if candidate.included:
            self._add_card(candidate)

    def _add_card(self, candidate: FrameCandidate) -> None:
        group = self._group_for(candidate.video_path)
        card = ScreenshotCardWidget(candidate)
        card.clicked.connect(self._on_card_clicked)
        card.double_clicked.connect(self._on_card_double_clicked)
        card.exclude_requested.connect(self._on_exclude)
        group.layout().addWidget(card)

        self.cards[candidate.id] = card
        self._card_order.append(candidate.id)
        self._render_card(candidate)

    def _group_for(self, video_path: str) -> QWidget:
        if video_path not in self._group_containers:
            header = QLabel(Path(video_path).name)
            header.setStyleSheet("font-weight:bold; padding-top:10px;")
            container = QWidget()
            container.setLayout(FlowLayout(spacing=10))

            insert_at = self.groups_layout.count() - 1
            self.groups_layout.insertWidget(insert_at, header)
            self.groups_layout.insertWidget(insert_at + 1, container)
            self._group_containers[video_path] = container
        return self._group_containers[video_path]

    def _render_card(self, candidate: FrameCandidate) -> None:
        slot = self.settings.logo_slots.get(candidate.logo_placement.slot_key)
        logo_path = slot.path if slot else None
        worker = CardRenderWorker(candidate, logo_path)
        worker.finished_render.connect(self._on_card_rendered)
        self._render_workers.append(worker)
        worker.start()

    def _on_card_rendered(self, candidate_id: str, image) -> None:
        card = self.cards.get(candidate_id)
        if card is None or image is None:
            return
        card.set_pixmap(QPixmap.fromImage(ImageQt(image)))

    # -- Selection -------------------------------------------------------

    def _on_card_clicked(self, candidate_id: str, modifiers) -> None:
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier) or bool(
            modifiers & Qt.KeyboardModifier.MetaModifier
        )
        shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        if shift and self.anchor_id is not None and self.anchor_id in self._card_order:
            self._select_range(self.anchor_id, candidate_id)
        elif ctrl:
            if candidate_id in self.selected_ids:
                self.selected_ids.discard(candidate_id)
            else:
                self.selected_ids.add(candidate_id)
            self.anchor_id = candidate_id
        else:
            self.selected_ids = set() if self.selected_ids == {candidate_id} else {candidate_id}
            self.anchor_id = candidate_id

        self._refresh_selection_styles()

    def _select_range(self, anchor_id: str, target_id: str) -> None:
        try:
            start = self._card_order.index(anchor_id)
            end = self._card_order.index(target_id)
        except ValueError:
            return
        low, high = sorted((start, end))
        self.selected_ids = set(self._card_order[low : high + 1])
        self._refresh_selection_styles()

    def _refresh_selection_styles(self) -> None:
        for candidate_id, card in self.cards.items():
            card.set_selected(candidate_id in self.selected_ids)

    def _candidate_by_id(self, candidate_id: str) -> FrameCandidate | None:
        for candidate in self.capture_store.frames:
            if candidate.id == candidate_id:
                return candidate
        return None

    # -- Detail dialog ---------------------------------------------------

    def _on_card_double_clicked(self, candidate_id: str) -> None:
        candidate = self._candidate_by_id(candidate_id)
        if candidate is None:
            return
        dialog = FrameDetailDialog(candidate, self.settings, self)
        dialog.exec()
        self._render_card(candidate)

    # -- Exclude -----------------------------------------------------------

    def _on_exclude(self, candidate_id: str) -> None:
        candidate = self._candidate_by_id(candidate_id)
        if candidate is not None:
            candidate.included = False
        card = self.cards.pop(candidate_id, None)
        if card is not None:
            card.setParent(None)
            card.deleteLater()
        self.selected_ids.discard(candidate_id)
        if candidate_id in self._card_order:
            self._card_order.remove(candidate_id)
        log_ui_action(logger, "exclude_frame")

    # -- Logo assignment panel -------------------------------------------

    def _apply_side(self, side: str) -> None:
        self._reassign_selected(lambda aspect, orientation, _side: build_slot_key(aspect, orientation, side))
        log_ui_action(logger, "assign_logo_side", side)

    def _apply_aspect(self, aspect: str) -> None:
        self._reassign_selected(lambda _aspect, orientation, side: build_slot_key(aspect, orientation, side))
        log_ui_action(logger, "assign_logo_aspect", aspect)

    def _reassign_selected(self, build_key) -> None:
        for candidate_id in list(self.selected_ids):
            candidate = self._candidate_by_id(candidate_id)
            if candidate is None:
                continue
            aspect, orientation, side = parse_slot_key(candidate.logo_placement.slot_key)
            new_key = build_key(aspect, orientation, side)
            slot = self.settings.logo_slots.get(new_key)
            if slot is None:
                continue
            candidate.logo_placement = LogoPlacement(
                slot_key=new_key, offset_x=slot.offset_x, offset_y=slot.offset_y, scale=slot.scale
            )
            self._render_card(candidate)

    # -- HDR fix -----------------------------------------------------------

    def shutdown(self) -> None:
        """Waits out any still-running card render threads — call before the
        window closes. Destroying a QThread while it's still running aborts
        the process."""
        for worker in self._render_workers:
            worker.wait()

    def _toggle_hdr_fix(self) -> None:
        selected = [self._candidate_by_id(cid) for cid in self.selected_ids]
        selected = [c for c in selected if c is not None]
        if not selected:
            return
        turn_on = not all(c.hdr_fix for c in selected)
        for candidate in selected:
            candidate.hdr_fix = turn_on
            self._render_card(candidate)
        log_ui_action(logger, "toggle_hdr_fix", f"on={turn_on} count={len(selected)}")
