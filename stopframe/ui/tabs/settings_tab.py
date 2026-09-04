"""Tab 1 — Setup: source videos, logo slots, export prefix.

Loading and probing source videos, editing the 4 logo slots, and setting
the export prefix all persist to Settings immediately on change, matching
the spec's "remembered between launches" requirement. The "Run automatic
pick" button is a structural stub — the analysis engine lands in a later
phase.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stopframe.config import LOGO_SLOT_KEYS, Settings, save_settings
from stopframe.core.models import VideoItem
from stopframe.core.video_probe import find_videos_in_folder, probe_video
from stopframe.logging_setup import get_logger, log_error, log_ui_action
from stopframe.ui.widgets.logo_slot_widget import LogoSlotWidget

logger = get_logger("ui.settings_tab")


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


class SettingsTab(QWidget):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.videos: list[VideoItem] = []

        content = QWidget()
        content_layout = QVBoxLayout(content)
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
        grid = QGridLayout(box)
        for index, key in enumerate(LOGO_SLOT_KEYS):
            slot_widget = LogoSlotWidget(key, self.settings.logo_slots[key])
            slot_widget.changed.connect(self._on_logo_slot_changed)
            grid.addWidget(slot_widget, index // 2, index % 2)
        return box

    def _on_logo_slot_changed(self) -> None:
        save_settings(self.settings)

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

        layout = QVBoxLayout(box)
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("Prefix"))
        prefix_row.addWidget(self.prefix_edit, stretch=1)
        layout.addLayout(prefix_row)
        layout.addWidget(self.prefix_before_radio)
        layout.addWidget(self.prefix_after_radio)
        return box

    def _on_prefix_changed(self, text: str) -> None:
        self.settings.export_prefix = text
        save_settings(self.settings)

    def _on_prefix_position_changed(self, checked: bool) -> None:
        self.settings.prefix_before_name = self.prefix_before_radio.isChecked()
        save_settings(self.settings)

    # -- Auto pick (stub) ------------------------------------------------

    def _build_auto_pick_box(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        self.auto_pick_button = QPushButton("Run Automatic Pick")
        self.auto_pick_button.clicked.connect(self._on_auto_pick_clicked)
        self.auto_pick_progress = QProgressBar()
        self.auto_pick_progress.setValue(0)
        layout.addWidget(self.auto_pick_button)
        layout.addWidget(self.auto_pick_progress)
        return box

    def _on_auto_pick_clicked(self) -> None:
        log_ui_action(logger, "run_automatic_pick")
        logger.info("Automatic pick requested but not yet implemented")
