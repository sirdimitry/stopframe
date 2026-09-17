"""Tab 2 — Timeline: per-video filmstrip, playhead, and manual capture.

One row per video, each with its own scrubbable filmstrip. The single
preview always shows the active row's video, live-composited with its
default logo placement — exactly what a capture or export would produce.
Space captures the current frame; Left/Right step it one frame at a time.
Keyboard shortcuts are only armed while this tab is actually visible
(see set_shortcuts_enabled), so they don't fire from other tabs.
"""

from __future__ import annotations

from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QMessageBox, QScrollArea, QVBoxLayout, QWidget

from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.compositor import compose_logo, frame_to_image, pick_slot_key
from stopframe.core.frame_reader import FrameSource
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement, VideoItem
from stopframe.logging_setup import get_logger, log_ui_action
from stopframe.ui.widgets.scroll_utils import enable_inertial_scroll
from stopframe.ui.widgets.timeline_row_widget import TimelineRowWidget
from stopframe.ui.workers.thumbnail_worker import ThumbnailWorker

logger = get_logger("ui.timeline_tab")

THUMBNAIL_COUNT = 60
PREVIEW_WIDTH = 420


class TimelineTab(QWidget):
    def __init__(
        self,
        videos: list[VideoItem],
        settings: Settings,
        capture_store: CaptureStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.videos = videos
        self.settings = settings
        self.capture_store = capture_store
        self.rows: list[TimelineRowWidget] = []
        self.active_index: int | None = None
        self.frame_source: FrameSource | None = None
        self._thumbnail_workers: list[ThumbnailWorker] = []

        self.now_previewing_label = QLabel("No video selected")
        self.now_previewing_label.setProperty("class", "caption")

        self.preview_label = QLabel("No video selected")
        self.preview_label.setObjectName("previewSurface")
        self.preview_label.setMinimumSize(320, 180)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.capture_button = QPushButton("Capture Frame  (Space)")
        self.capture_button.setObjectName("primaryButton")
        self.capture_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.capture_button.setMinimumHeight(48)
        self.capture_button.clicked.connect(self._on_capture_clicked)

        preview_container = QWidget()
        preview_container.setFixedWidth(PREVIEW_WIDTH)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setSpacing(10)
        preview_layout.setContentsMargins(0, 0, 12, 0)
        preview_layout.addWidget(self.now_previewing_label)
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.capture_button)
        preview_layout.addStretch(1)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setSpacing(20)
        self.rows_layout.addStretch(1)

        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setWidget(self.rows_container)
        enable_inertial_scroll(rows_scroll)

        main_layout = QHBoxLayout(self)
        main_layout.addWidget(preview_container)
        main_layout.addWidget(rows_scroll, stretch=1)

        self._shortcuts = self._install_shortcuts()
        self.capture_store.frame_added.connect(self._on_frame_added)

        self.refresh()

    # -- Row management ----------------------------------------------------

    def refresh(self) -> None:
        existing_paths = {row.video.path for row in self.rows}
        for video in self.videos:
            if video.path not in existing_paths:
                self._add_row(video)

    def _add_row(self, video: VideoItem) -> None:
        row = TimelineRowWidget(video)
        row.activated.connect(lambda v=video: self._on_row_activated(v))
        row.position_changed.connect(lambda fraction, v=video: self._on_position_changed(v, fraction))
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, row)
        self.rows.append(row)
        row.filmstrip.set_markers(self.capture_store.markers_for(video.path))

        worker = ThumbnailWorker(video.path, THUMBNAIL_COUNT)
        worker.finished_with_thumbnails.connect(self._on_thumbnails_ready)
        self._thumbnail_workers.append(worker)
        worker.start()

        if self.active_index is None:
            self._on_row_activated(video)

    def _on_thumbnails_ready(self, video_path: str, thumbnails: list) -> None:
        for row in self.rows:
            if row.video.path == video_path:
                row.filmstrip.set_thumbnails(thumbnails)
                break

    def _row_index(self, video: VideoItem) -> int | None:
        for index, row in enumerate(self.rows):
            if row.video.path == video.path:
                return index
        return None

    def remove_video(self, video_path: str) -> None:
        index = next((i for i, row in enumerate(self.rows) if row.video.path == video_path), None)
        if index is None:
            return
        row = self.rows.pop(index)
        self.rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()

        if self.active_index == index:
            if self.frame_source is not None:
                self.frame_source.close()
                self.frame_source = None
            self.active_index = None
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("No video selected")
            self.now_previewing_label.setText("No video selected")
        elif self.active_index is not None and self.active_index > index:
            self.active_index -= 1

    # -- Activation / preview ----------------------------------------------

    def _on_row_activated(self, video: VideoItem) -> None:
        index = self._row_index(video)
        if index is None:
            return
        if index != self.active_index:
            self.active_index = index
            for row_index, row in enumerate(self.rows):
                row.set_active(row_index == index)
            if self.frame_source is not None:
                self.frame_source.close()
            self.frame_source = FrameSource(video.path)
            self._apply_preview_aspect(video)
            self.now_previewing_label.setText(f"Now previewing: {video.file_name}")
        self._update_preview()

    def _apply_preview_aspect(self, video: VideoItem) -> None:
        """Sizes the preview box to the active video's own aspect ratio
        instead of always filling the panel's full height — a landscape
        video no longer sits in a mostly-empty tall box."""
        if video.width <= 0 or video.height <= 0:
            return
        label_width = PREVIEW_WIDTH - 20
        label_height = round(label_width * video.height / video.width)
        self.preview_label.setFixedSize(label_width, label_height)

    def _on_position_changed(self, video: VideoItem, fraction: float) -> None:
        self._on_row_activated(video)

    def _active_video(self) -> VideoItem | None:
        if self.active_index is None:
            return None
        return self.rows[self.active_index].video

    def _default_placement(self, video: VideoItem) -> LogoPlacement:
        slot_key = pick_slot_key(video.aspect_ratio, video.orientation, "left")
        slot = self.settings.logo_slots[slot_key]
        return LogoPlacement(slot_key=slot_key, offset_x=slot.offset_x, offset_y=slot.offset_y, scale=slot.scale)

    def _timestamp_at_playhead(self, video: VideoItem) -> float:
        fraction = self.rows[self.active_index].filmstrip.position_fraction
        last_timestamp = max(0.0, video.duration_seconds - (1 / video.fps if video.fps > 0 else 0.001))
        return min(fraction * video.duration_seconds, last_timestamp)

    def _update_preview(self) -> None:
        video = self._active_video()
        if video is None or self.frame_source is None or self.active_index is None:
            return
        timestamp = self._timestamp_at_playhead(video)
        frame_bgr = self.frame_source.read_at(timestamp)
        if frame_bgr is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Could not read frame")
            return

        image = frame_to_image(frame_bgr)
        placement = self._default_placement(video)
        slot = self.settings.logo_slots.get(placement.slot_key)
        logo_path = slot.path if slot else None
        composed = compose_logo(image, logo_path, placement)

        pixmap = QPixmap.fromImage(ImageQt(composed))
        scaled = pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    # -- Capture -------------------------------------------------------

    def _on_capture_clicked(self) -> None:
        video = self._active_video()
        if video is None or self.active_index is None:
            return
        timestamp = self._timestamp_at_playhead(video)
        if self.frame_source is None or self.frame_source.read_at(timestamp) is None:
            QMessageBox.warning(self, "Capture Frame", "Could not read this frame. Choose another position in the video.")
            return
        frame_index = round(timestamp * video.fps) if video.fps else 0
        placement = self._default_placement(video)
        candidate = FrameCandidate(
            video_path=video.path,
            frame_index=frame_index,
            timestamp_seconds=timestamp,
            origin=FrameOrigin.MANUAL,
            logo_placement=placement,
        )
        self.capture_store.add(candidate)
        log_ui_action(logger, "capture_frame", f"row={self.active_index}")

    def _on_frame_added(self, frame: FrameCandidate) -> None:
        for row in self.rows:
            if row.video.path == frame.video_path:
                row.filmstrip.set_markers(self.capture_store.markers_for(frame.video_path))
                break

    # -- Keyboard shortcuts --------------------------------------------

    def _install_shortcuts(self) -> list[QShortcut]:
        shortcuts = []
        capture_shortcut = QShortcut(QKeySequence("Space"), self)
        capture_shortcut.activated.connect(self._on_capture_clicked)
        shortcuts.append(capture_shortcut)

        step_back = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        step_back.activated.connect(lambda: self._step_frame(-1))
        shortcuts.append(step_back)

        step_forward = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        step_forward.activated.connect(lambda: self._step_frame(1))
        shortcuts.append(step_forward)

        return shortcuts

    def set_shortcuts_enabled(self, enabled: bool) -> None:
        for shortcut in self._shortcuts:
            shortcut.setEnabled(enabled)

    def shutdown(self) -> None:
        """Waits out any still-running thumbnail threads and releases the
        open video handle — call before the window closes. Destroying a
        QThread while its OS thread is still running aborts the process."""
        for worker in self._thumbnail_workers:
            worker.wait()
        if self.frame_source is not None:
            self.frame_source.close()
            self.frame_source = None

    def _step_frame(self, direction: int) -> None:
        video = self._active_video()
        if video is None or self.active_index is None or video.fps <= 0 or video.duration_seconds <= 0:
            return
        row = self.rows[self.active_index]
        timestamp = self._timestamp_at_playhead(video) + direction / video.fps
        row.filmstrip.set_position(timestamp / video.duration_seconds)
        self._update_preview()
