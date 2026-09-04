"""Top-level window: three tabs plus the Export button.

The Export button lives outside the QTabWidget (so it doesn't have to be
duplicated inside ScreenshotsTab) but is only shown while that tab is
active — exporting only makes sense once you're reviewing the screenshots
you've captured, not while still adding sources or scrubbing the timeline.
"""

from __future__ import annotations

import subprocess

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QMessageBox, QProgressDialog, QPushButton, QTabWidget, QVBoxLayout, QWidget

from stopframe import __version__
from stopframe.config import load_settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.models import VideoItem
from stopframe.logging_setup import get_logger, log_ui_action
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
from stopframe.ui.tabs.settings_tab import SettingsTab
from stopframe.ui.tabs.timeline_tab import TimelineTab
from stopframe.ui.workers.export_worker import ExportWorker

logger = get_logger("ui.main_window")

TIMELINE_TAB_INDEX = 1
SCREENSHOTS_TAB_INDEX = 2


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"StopFrame {__version__}")
        # Below this, the Timeline tab's fixed-width preview panel and row
        # label leave the filmstrip too narrow to be usable.
        self.setMinimumSize(950, 650)
        self.resize(1200, 800)

        self.settings = load_settings()
        self.videos: list[VideoItem] = []
        self.capture_store = CaptureStore()

        self.settings_tab = SettingsTab(self.settings, self.videos, self.capture_store)
        self.timeline_tab = TimelineTab(self.videos, self.settings, self.capture_store)
        self.screenshots_tab = ScreenshotsTab(self.capture_store, self.settings)

        self.settings_tab.videos_changed.connect(self.timeline_tab.refresh)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.settings_tab, "1. Setup")
        self.tabs.addTab(self.timeline_tab, "2. Timeline")
        self.tabs.addTab(self.screenshots_tab, "3. Screenshots")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.timeline_tab.set_shortcuts_enabled(self.tabs.currentIndex() == TIMELINE_TAB_INDEX)

        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("primaryButton")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.export_button.setVisible(self.tabs.currentIndex() == SCREENSHOTS_TAB_INDEX)
        self._export_worker: ExportWorker | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.tabs, stretch=1)
        layout.addWidget(self.export_button)
        self.setCentralWidget(central)

    def _on_tab_changed(self, index: int) -> None:
        log_ui_action(logger, "tab_switch", f"index={index}")
        self.timeline_tab.set_shortcuts_enabled(index == TIMELINE_TAB_INDEX)
        self.export_button.setVisible(index == SCREENSHOTS_TAB_INDEX)

    def _on_export_clicked(self) -> None:
        if self._export_worker is not None:
            return
        included = [frame for frame in self.capture_store.frames if frame.included]
        log_ui_action(logger, "export_button", f"frames={len(included)}")
        if not included:
            QMessageBox.information(self, "Export", "No captured frames to export yet.")
            return

        self.export_button.setEnabled(False)
        progress_dialog = QProgressDialog("Exporting frames…", "Cancel", 0, len(included), self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)

        worker = ExportWorker(included, self.settings)
        worker.progress.connect(progress_dialog.setValue)
        worker.finished_all.connect(lambda folders: self._on_export_finished(folders, progress_dialog))
        progress_dialog.canceled.connect(worker.request_cancel)
        self._export_worker = worker
        worker.start()

    def _on_export_finished(self, folders: list[str], progress_dialog: QProgressDialog) -> None:
        progress_dialog.close()
        self.export_button.setEnabled(True)
        self._export_worker = None
        log_ui_action(logger, "export_finished", f"folders={len(folders)}")
        for folder in folders:
            subprocess.Popen(["open", folder])

    def closeEvent(self, event) -> None:
        self.settings_tab.shutdown()
        self.timeline_tab.shutdown()
        self.screenshots_tab.shutdown()
        if self._export_worker is not None:
            self._export_worker.wait()
        super().closeEvent(event)
