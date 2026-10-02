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

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
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
from stopframe.ui.widgets.scroll_utils import enable_inertial_scroll
from stopframe.ui.workers.auto_pick_worker import AutoPickWorker

logger = get_logger("ui.settings_tab")


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


class SettingsTab(QWidget):
    videos_changed = Signal()
    logos_changed = Signal()
    video_removed = Signal(str)  # video_path

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
        self._auto_pick_cancel_requested = False
        self._current_auto_pick_videos: list[VideoItem] = []
        self._last_auto_pick_done = 0

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        content_layout.addWidget(self._build_source_box())
        self.logo_settings_dialog = QDialog(self)
        self.logo_settings_dialog.setWindowTitle("Logo Library")
        self.logo_settings_dialog.resize(560, 240)
        logo_layout = QVBoxLayout(self.logo_settings_dialog)
        logo_layout.addWidget(self._build_logos_box())
        done_button = QPushButton("Done")
        done_button.clicked.connect(self.logo_settings_dialog.accept)
        logo_layout.addWidget(done_button, alignment=Qt.AlignmentFlag.AlignRight)
        content_layout.addWidget(self._build_auto_pick_box())
        content_layout.addWidget(self._build_export_box())
        content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        enable_inertial_scroll(scroll)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        self._refresh_video_table()

    # -- Source ----------------------------------------------------------

    def _build_source_box(self) -> QGroupBox:
        box = QGroupBox("Исходные видео")
        add_folder_button = QPushButton("Добавить папку…")
        add_folder_button.clicked.connect(self._on_add_folder)
        add_file_button = QPushButton("Добавить видео…")
        add_file_button.clicked.connect(self._on_add_file)
        clear_all_button = QPushButton("Удалить все")
        clear_all_button.setObjectName("destructiveButton")
        clear_all_button.clicked.connect(self._clear_all_videos)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_folder_button)
        buttons_row.addWidget(add_file_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(clear_all_button)

        self.video_table = QTableWidget(0, 4)
        self.video_table.setHorizontalHeaderLabels(["Видео", "Разрешение", "Формат", "Длительность"])
        self.video_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.video_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.video_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.video_table.verticalHeader().setVisible(False)
        self.video_table.setAlternatingRowColors(True)
        self.video_table.setShowGrid(False)
        self.video_table.setMinimumHeight(180)
        self.video_table.setMaximumHeight(320)
        self.video_table.verticalHeader().setDefaultSectionSize(38)
        self.video_table.installEventFilter(self)

        self.source_hint = QLabel("Начните с видео или папки. Поддерживаются MP4, MOV, M4V, AVI и MKV.")
        self.source_hint.setProperty("class", "caption")
        self.source_hint.setWordWrap(True)
        hint = QLabel("Выделите строку и нажмите Delete, чтобы удалить видео и связанные кадры.")
        hint.setProperty("class", "caption")
        hint.setWordWrap(True)

        layout = QVBoxLayout(box)
        layout.addLayout(buttons_row)
        layout.addWidget(self.source_hint)
        layout.addWidget(self.video_table)
        layout.addWidget(hint)
        return box

    def eventFilter(self, watched, event) -> bool:
        if watched is getattr(self, "frames_per_video_spin", None) and event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        if (
            watched is self.video_table
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
        ):
            self._delete_selected_videos()
            return True
        return super().eventFilter(watched, event)

    def _delete_selected_videos(self) -> None:
        rows = sorted({index.row() for index in self.video_table.selectedIndexes()}, reverse=True)
        to_remove = [self.videos[row] for row in rows if 0 <= row < len(self.videos)]
        if not to_remove:
            return

        analysis_running = self._auto_pick_worker is not None
        screenshot_count = sum(self.capture_store.count_for(v.path) for v in to_remove)

        if analysis_running or screenshot_count:
            plural_v = "s" if len(to_remove) != 1 else ""
            names = ", ".join(v.file_name for v in to_remove)
            message_parts = [f"Remove {len(to_remove)} video{plural_v} ({names})?"]
            if analysis_running:
                message_parts.append("Automatic Pick is currently running — this will stop it first.")
            if screenshot_count:
                plural_s = "s" if screenshot_count != 1 else ""
                message_parts.append(
                    f"This will also delete {screenshot_count} screenshot{plural_s} already made from "
                    f"{'them' if len(to_remove) != 1 else 'it'}."
                )
            answer = QMessageBox.question(
                self,
                "Remove Videos",
                " ".join(message_parts),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            if analysis_running:
                self._stop_auto_pick()

        for video in to_remove:
            self.videos.remove(video)
            self._auto_picked_paths.discard(video.path)
            self.capture_store.remove_video(video.path)
            self.video_removed.emit(video.path)

        self._refresh_video_table()
        log_ui_action(logger, "remove_videos", f"count={len(to_remove)} analysis_running={analysis_running}")

    def _clear_all_videos(self) -> None:
        if not self.videos:
            return
        self.video_table.selectAll()
        self._delete_selected_videos()

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
        self.source_hint.setText(f"Добавлено видео: {len(self.videos)}" if self.videos else "Начните с видео или папки. Поддерживаются MP4, MOV, M4V, AVI и MKV.")
        if self._auto_pick_worker is None:
            self.auto_pick_button.setEnabled(bool(self.videos))
        self.auto_pick_button.setToolTip("Подобрать резкие и непохожие кадры" if self.videos else "Добавьте видео, чтобы запустить отбор")
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
        choose_button.clicked.connect(self._on_choose_logos_folder)

        self.logos_folder_label = QLabel("No folder chosen")
        self.logos_folder_label.setProperty("class", "caption")
        self.logos_folder_label.setWordWrap(True)

        self.logos_status_label = QLabel()
        self.logos_status_label.setProperty("class", "caption")
        self.logos_status_label.setWordWrap(True)

        layout = QVBoxLayout(box)
        layout.setSpacing(8)
        layout.addWidget(choose_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.logos_folder_label)
        layout.addWidget(self.logos_status_label)

        if self.settings.logos_folder:
            self._rescan_logos_folder(self.settings.logos_folder, persist=False)
        else:
            self._refresh_logos_status()

        return box

    def _on_choose_logos_folder(self) -> None:
        start_dir = self.settings.logos_folder or ""
        folder = QFileDialog.getExistingDirectory(self.logo_settings_dialog, "Choose Logos Folder", start_dir)
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
        self.logos_changed.emit()
        logger.info(f"Matched {len(matches)}/{len(LOGO_SLOT_KEYS)} logo slot(s) from folder")
        if persist:
            save_settings(self.settings)

    def show_logo_settings(self) -> None:
        self.logo_settings_dialog.exec()

    def _refresh_logos_status(self) -> None:
        loaded = sum(1 for key in LOGO_SLOT_KEYS if self.settings.logo_slots[key].path and Path(self.settings.logo_slots[key].path).is_file())
        total = len(LOGO_SLOT_KEYS)
        if loaded == 0:
            self.logos_status_label.setText("No logos loaded")
        else:
            self.logos_status_label.setText(f"{loaded} of {total} logos loaded")

    # -- Export --------------------------------------------------------

    def _build_export_box(self) -> QGroupBox:
        box = QGroupBox("Параметры экспорта")

        self.prefix_edit = QLineEdit(self.settings.export_prefix)
        self.prefix_edit.setPlaceholderText("prefix")
        self.prefix_edit.textChanged.connect(self._on_prefix_changed)

        self.prefix_before_radio = QRadioButton("Перед именем (префикс-ИМЯ)")
        self.prefix_after_radio = QRadioButton("После имени (ИМЯ-префикс)")
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
        prefix_row.addWidget(QLabel("Префикс"))
        prefix_row.addWidget(self.prefix_edit, stretch=1)
        layout.addLayout(prefix_row)

        prefix_position_row = QHBoxLayout()
        prefix_position_row.addWidget(self.prefix_before_radio)
        prefix_position_row.addWidget(self.prefix_after_radio)
        prefix_position_row.addStretch(1)
        layout.addLayout(prefix_position_row)

        format_row = QHBoxLayout()
        format_row.addWidget(QLabel("Формат"))
        format_row.addWidget(self.format_combo)
        format_row.addWidget(QLabel("Качество JPEG"))
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
        box = QGroupBox("Автоматический отбор")
        layout = QVBoxLayout(box)

        controls_row = QHBoxLayout()
        self.auto_pick_button = QPushButton("Подобрать кадры")
        self.auto_pick_button.setObjectName("primaryButton")
        self.auto_pick_button.setEnabled(bool(self.videos))
        self.auto_pick_button.clicked.connect(self._on_auto_pick_clicked)
        controls_row.addWidget(self.auto_pick_button)
        self.stop_auto_pick_button = QPushButton("Остановить")
        self.stop_auto_pick_button.setEnabled(False)
        self.stop_auto_pick_button.clicked.connect(self._stop_auto_pick)
        controls_row.addWidget(self.stop_auto_pick_button)
        controls_row.addWidget(QLabel("Максимум кадров из видео"))
        self.frames_per_video_spin = QSpinBox()
        self.frames_per_video_spin.setRange(MIN_PICKS, MAX_PICKS)
        self.frames_per_video_spin.setValue(self.settings.frames_per_video)
        self.frames_per_video_spin.installEventFilter(self)
        self.frames_per_video_spin.valueChanged.connect(self._on_frames_per_video_changed)
        controls_row.addWidget(self.frames_per_video_spin)
        controls_row.addStretch(1)

        self.auto_pick_status_label = QLabel("")
        self.auto_pick_status_label.setProperty("class", "caption")
        self.auto_pick_progress = QProgressBar()
        self.auto_pick_progress.setValue(0)

        layout.addLayout(controls_row)
        hint = QLabel("Отбор учитывает резкость, разнообразие и выражения лиц. "
                      "Кадров может быть меньше указанного максимума — проверьте результат перед экспортом.")
        hint.setWordWrap(True)
        hint.setProperty("class", "caption")
        layout.addWidget(hint)
        layout.addWidget(self.auto_pick_status_label)
        layout.addWidget(self.auto_pick_progress)
        return box

    def _on_frames_per_video_changed(self, value: int) -> None:
        self.settings.frames_per_video = value
        save_settings(self.settings)

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
        self.frames_per_video_spin.setEnabled(False)
        self.stop_auto_pick_button.setEnabled(True)
        self.auto_pick_progress.setMaximum(len(videos))
        self.auto_pick_progress.setValue(0)
        self.auto_pick_status_label.setText(f"0 / {len(videos)} videos analyzed")

        self._auto_pick_cancel_requested = False
        self._current_auto_pick_videos = videos
        self._last_auto_pick_done = 0
        self._auto_picked_paths.update(v.path for v in videos)

        worker = AutoPickWorker(videos, self.settings, self.frames_per_video_spin.value())
        worker.candidate_ready.connect(self._on_auto_pick_candidate)
        worker.progress.connect(self._on_auto_pick_progress)
        worker.status.connect(self._on_auto_pick_status)
        worker.finished_all.connect(self._on_auto_pick_finished)
        self._auto_pick_worker = worker
        worker.start()

    def _stop_auto_pick(self) -> None:
        """Requests cancellation and disables the Stop button immediately
        so a second click can't fire — the worker confirms via
        finished_all once it actually notices (see AutoPickWorker)."""
        if self._auto_pick_worker is None:
            return
        self._auto_pick_cancel_requested = True
        self._auto_pick_worker.request_cancel()
        self.stop_auto_pick_button.setEnabled(False)
        self.auto_pick_status_label.setText("Stopping…")
        log_ui_action(logger, "stop_automatic_pick")

    def _on_auto_pick_candidate(self, candidate) -> None:
        # A video can be deleted out from under a still-finishing worker
        # (its cancellation takes effect within roughly one frame's worth
        # of I/O, not instantly) — drop any straggling result for a video
        # that's no longer in the source list rather than resurrecting it.
        if any(v.path == candidate.video_path for v in self.videos):
            self.capture_store.add(candidate)

    def _on_auto_pick_status(self, text: str) -> None:
        if not self._auto_pick_cancel_requested:
            self.auto_pick_status_label.setText(text)

    def _on_auto_pick_progress(self, done: int, total: int) -> None:
        self._last_auto_pick_done = done
        self.auto_pick_progress.setValue(done)
        if not self._auto_pick_cancel_requested:
            self.auto_pick_status_label.setText(f"{done} / {total} videos analyzed")

    def _on_auto_pick_finished(self) -> None:
        log_ui_action(logger, "automatic_pick_finished", f"cancelled={self._auto_pick_cancel_requested}")
        if self._auto_pick_cancel_requested:
            # Only the videos actually completed before the stop count as
            # "picked" — the rest (including whichever one was mid-scan)
            # should be eligible for a plain, unprompted re-run.
            completed_paths = {v.path for v in self._current_auto_pick_videos[: self._last_auto_pick_done]}
            attempted_paths = {v.path for v in self._current_auto_pick_videos}
            self._auto_picked_paths -= attempted_paths - completed_paths
            self.auto_pick_status_label.setText(
                f"Stopped — {self._last_auto_pick_done} / {len(self._current_auto_pick_videos)} videos analyzed"
            )
        self.auto_pick_button.setEnabled(bool(self.videos))
        self.frames_per_video_spin.setEnabled(True)
        self.stop_auto_pick_button.setEnabled(False)
        worker = self._auto_pick_worker
        if worker is not None:
            worker.wait()
            if not worker.face_checks_available:
                self.auto_pick_status_label.setText(
                    self.auto_pick_status_label.text() + " — Face checks unavailable; selected by sharpness and diversity only."
                )
        self._auto_pick_worker = None
        self._auto_pick_cancel_requested = False
        self._current_auto_pick_videos = []
        self._last_auto_pick_done = 0

    def shutdown(self) -> None:
        """Waits out a still-running auto-pick pass before the window
        closes — destroying a running QThread aborts the process. Cancels
        first so this doesn't sit blocking the whole app for as long as a
        huge source video's analysis would otherwise take."""
        if self._auto_pick_worker is not None:
            self._auto_pick_worker.request_cancel()
            self._auto_pick_worker.wait()
        face_check.shutdown()
