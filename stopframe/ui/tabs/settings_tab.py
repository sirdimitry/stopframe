"""Tab 1 — Setup: source videos, logo slots, export prefix, auto pick.

Loading and probing source videos, matching logo overlays, and setting
the export prefix all persist to Settings immediately on change, matching
the spec's "remembered between launches" requirement. "Run Automatic Pick"
runs the auto-analysis engine across all source videos in the background
and streams results into the shared CaptureStore, same as a manual capture
from the Timeline tab.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import LOGO_SLOT_KEYS, Settings, save_settings
from stopframe.core import face_check
from stopframe.core.auto_pick import MAX_PICKS, MIN_PICKS
from stopframe.core.capture_store import CaptureStore
from stopframe.core.logo_matcher import match_logos_in_folder
from stopframe.core.models import VideoItem
from stopframe.core.video_probe import find_videos_in_folder, probe_video
from stopframe.logging_setup import get_logger, log_error, log_ui_action
from stopframe.ui.workers.auto_pick_worker import AutoPickWorker

logger = get_logger("ui.settings_tab")


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


class SettingsTab(QWidget):
    videos_changed = Signal()

    def __init__(
        self,
        settings: Settings,
        videos: list[VideoItem],
        capture_store: CaptureStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.videos = videos
        self.capture_store = capture_store
        self._auto_pick_worker: AutoPickWorker | None = None
        self._auto_picked_paths: set[str] = set()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        content_layout.addWidget(self._build_source_box())
        content_layout.addWidget(self._build_logos_box())
        content_layout.addWidget(self._build_export_box())
        content_layout.addWidget(self._build_auto_pick_box())
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

    # -- Source ----------------------------------------------------------

    def _build_source_box(self) -> QGroupBox:
        box = QGroupBox("Source")
        add_folder_button = QPushButton("Add Folder…")
        add_folder_button.clicked.connect(self._on_add_folder)
        add_file_button = QPushButton("Add File…")
        add_file_button.clicked.connect(self._on_add_file)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_folder_button)
        buttons_row.addWidget(add_file_button)
        buttons_row.addStretch(1)

        self.video_table = QTableWidget(0, 4)
        self.video_table.setHorizontalHeaderLabels(["File", "Resolution", "Aspect", "Duration"])
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.setShowGrid(False)
        self.video_table.verticalHeader().setDefaultSectionSize(28)

        layout = QVBoxLayout(box)
        layout.addLayout(buttons_row)
        layout.addWidget(self.video_table)
        return box

    def _on_add_folder(self) -> None:
        start_dir = self.settings.last_video_folder or ""
        folder = QFileDialog.getExistingDirectory(self, "Add Folder", start_dir)
        if not folder:
            return
        log_ui_action(logger, "add_folder")
        paths = find_videos_in_folder(folder)
        self._add_video_paths(paths)
        self.settings.last_video_folder = folder
        save_settings(self.settings)

    def _on_add_file(self) -> None:
        start_dir = self.settings.last_video_folder or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Add Video", start_dir, "Video Files (*.mp4 *.mov *.m4v *.avi *.mkv)"
        )
        if not path:
            return
        log_ui_action(logger, "add_file")
        self._add_video_paths([path])
        self.settings.last_video_folder = str(Path(path).parent)
        save_settings(self.settings)

    def _add_video_paths(self, paths: list[str]) -> None:
        known = {video.path for video in self.videos}
        added = 0
        for path in paths:
            if path in known:
                continue
            item = probe_video(path)
            if item is None:
                log_error(logger, "video_probe", ValueError(Path(path).name))
                continue
            self.videos.append(item)
            added += 1
        self._refresh_video_table()
        logger.info(f"Added {added} video(s), {len(self.videos)} total")
        if added:
            self.videos_changed.emit()

    def _refresh_video_table(self) -> None:
        self.video_table.setRowCount(len(self.videos))
        for row, video in enumerate(self.videos):
            self.video_table.setItem(row, 0, QTableWidgetItem(video.file_name))
            self.video_table.setItem(row, 1, QTableWidgetItem(f"{video.width}x{video.height}"))
            self.video_table.setItem(row, 2, QTableWidgetItem(video.aspect_ratio.value))
            self.video_table.setItem(row, 3, QTableWidgetItem(_format_duration(video.duration_seconds)))

    # -- Logos -------------------------------------------------------------

    def _build_logos_box(self) -> QGroupBox:
        box = QGroupBox("Logos")

        choose_button = QPushButton("Choose Logos Folder…")
        choose_button.setObjectName("primaryButton")
        choose_button.clicked.connect(self._on_choose_logos_folder)

        self.logos_folder_label = QLabel("No folder chosen")
        self.logos_folder_label.setProperty("class", "caption")
        self.logos_folder_label.setWordWrap(True)

        self.logos_status_label = QLabel()
        self.logos_status_label.setProperty("class", "caption")
        self.logos_status_label.setWordWrap(True)

        layout = QVBoxLayout(box)
        layout.setSpacing(8)
        layout.addWidget(choose_button)
        layout.addWidget(self.logos_folder_label)
        layout.addWidget(self.logos_status_label)

        if self.settings.logos_folder:
            self._rescan_logos_folder(self.settings.logos_folder, persist=False)
        else:
            self._refresh_logos_status()

        return box

    def _on_choose_logos_folder(self) -> None:
        start_dir = self.settings.logos_folder or ""
        folder = QFileDialog.getExistingDirectory(self, "Choose Logos Folder", start_dir)
        if not folder:
            return
        log_ui_action(logger, "choose_logos_folder")
        self._rescan_logos_folder(folder, persist=True)

    def _rescan_logos_folder(self, folder: str, persist: bool) -> None:
        matches = match_logos_in_folder(folder)
        for key in LOGO_SLOT_KEYS:
            self.settings.logo_slots[key].path = matches.get(key)
        self.settings.logos_folder = folder
        self.logos_folder_label.setText(folder)
        self._refresh_logos_status()
        logger.info(f"Matched {len(matches)}/{len(LOGO_SLOT_KEYS)} logo slot(s) from folder")
        if persist:
            save_settings(self.settings)

    def _refresh_logos_status(self) -> None:
        lines = []
        for key in LOGO_SLOT_KEYS:
            path = self.settings.logo_slots[key].path
            mark = "✓" if path else "✗"
            name = Path(path).name if path else "not found"
            lines.append(f"{mark} {key} — {name}")
        self.logos_status_label.setText("\n".join(lines))

    # -- Export --------------------------------------------------------

    def _build_export_box(self) -> QGroupBox:
        box = QGroupBox("Export")

        self.prefix_edit = QLineEdit(self.settings.export_prefix)
        self.prefix_edit.setPlaceholderText("prefix")
        self.prefix_edit.textChanged.connect(self._on_prefix_changed)

        self.prefix_before_radio = QRadioButton("Before name (prefix-NAME)")
        self.prefix_after_radio = QRadioButton("After name (NAME-prefix)")
        if self.settings.prefix_before_name:
            self.prefix_before_radio.setChecked(True)
        else:
            self.prefix_after_radio.setChecked(True)
        self.prefix_before_radio.toggled.connect(self._on_prefix_position_changed)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "JPEG"])
        self.format_combo.setCurrentText(self.settings.export_format)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(self.settings.jpeg_quality)
        self.jpeg_quality_spin.valueChanged.connect(self._on_jpeg_quality_changed)
        self.jpeg_quality_spin.setEnabled(self.settings.export_format == "JPEG")

        layout = QVBoxLayout(box)
        layout.setSpacing(10)
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Prefix"))
        prefix_row.addWidget(self.prefix_edit, stretch=1)
        layout.addLayout(prefix_row)

        prefix_position_row = QHBoxLayout()
        prefix_position_row.addWidget(self.prefix_before_radio)
        prefix_position_row.addWidget(self.prefix_after_radio)
        prefix_position_row.addStretch(1)
        layout.addLayout(prefix_position_row)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Format"))
        format_row.addWidget(self.format_combo)
        format_row.addWidget(QLabel("JPEG quality"))
        format_row.addWidget(self.jpeg_quality_spin)
        format_row.addStretch(1)
        layout.addLayout(format_row)
        return box

    def _on_format_changed(self, text: str) -> None:
        self.settings.export_format = text
        self.jpeg_quality_spin.setEnabled(text == "JPEG")
        save_settings(self.settings)

    def _on_jpeg_quality_changed(self, value: int) -> None:
        self.settings.jpeg_quality = value
        save_settings(self.settings)

    def _on_prefix_changed(self, text: str) -> None:
        self.settings.export_prefix = text
        save_settings(self.settings)

    def _on_prefix_position_changed(self, checked: bool) -> None:
        self.settings.prefix_before_name = self.prefix_before_radio.isChecked()
        save_settings(self.settings)

    # -- Auto pick -----------------------------------------------------

    def _build_auto_pick_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)

        controls_row = QHBoxLayout()
        self.auto_pick_button = QPushButton("Run Automatic Pick")
        self.auto_pick_button.setObjectName("primaryButton")
        self.auto_pick_button.clicked.connect(self._on_auto_pick_clicked)
        controls_row.addWidget(self.auto_pick_button)
        controls_row.addWidget(QLabel("Frames per video"))
        self.frames_per_video_spin = QSpinBox()
        self.frames_per_video_spin.setRange(MIN_PICKS, MAX_PICKS)
        self.frames_per_video_spin.setValue(4)
        controls_row.addWidget(self.frames_per_video_spin)
        controls_row.addStretch(1)

        self.auto_pick_status_label = QLabel("")
        self.auto_pick_status_label.setProperty("class", "caption")
        self.auto_pick_progress = QProgressBar()
        self.auto_pick_progress.setValue(0)

        layout.addLayout(controls_row)
        layout.addWidget(self.auto_pick_status_label)
        layout.addWidget(self.auto_pick_progress)
        return box

    def _on_auto_pick_clicked(self) -> None:
        if not self.videos or self._auto_pick_worker is not None:
            return

        pending = [v for v in self.videos if v.path not in self._auto_picked_paths]
        if pending:
            self._start_auto_pick(pending)
            return

        # Every video already has automatic picks — redoing means duplicate
        # screenshots for all of them, so confirm before doing it again.
        answer = QMessageBox.question(
            self,
            "Run Automatic Pick",
            "Screenshots have already been picked for every video. Run automatic pick again for all of them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_auto_pick(list(self.videos))

    def _start_auto_pick(self, videos: list[VideoItem]) -> None:
        log_ui_action(logger, "run_automatic_pick", f"videos={len(videos)}")

        self.auto_pick_button.setEnabled(False)
        self.auto_pick_progress.setMaximum(len(videos))
        self.auto_pick_progress.setValue(0)
        self.auto_pick_status_label.setText(f"0 / {len(videos)} videos analyzed")

        self._auto_picked_paths.update(v.path for v in videos)

        worker = AutoPickWorker(videos, self.settings, self.frames_per_video_spin.value())
        worker.candidate_ready.connect(self.capture_store.add)
        worker.progress.connect(self._on_auto_pick_progress)
        worker.finished_all.connect(self._on_auto_pick_finished)
        self._auto_pick_worker = worker
        worker.start()

    def _on_auto_pick_progress(self, done: int, total: int) -> None:
        self.auto_pick_progress.setValue(done)
        self.auto_pick_status_label.setText(f"{done} / {total} videos analyzed")

    def _on_auto_pick_finished(self) -> None:
        log_ui_action(logger, "automatic_pick_finished")
        self.auto_pick_button.setEnabled(True)
        self._auto_pick_worker = None

    def shutdown(self) -> None:
        """Waits out a still-running auto-pick pass before the window
        closes — destroying a running QThread aborts the process."""
        if self._auto_pick_worker is not None:
            self._auto_pick_worker.wait()
        face_check.shutdown()
