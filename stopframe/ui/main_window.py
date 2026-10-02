"""Top-level window: three tabs plus the Export button.

The Export button lives outside the QTabWidget (so it doesn't have to be
duplicated inside ScreenshotsTab) but is only shown while that tab is
active — exporting only makes sense once you're reviewing the screenshots
you've captured, not while still adding sources or scrubbing the timeline.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from stopframe import __version__
from stopframe.ui.widgets.about_dialog import AboutDialog
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
        available = self.screen().availableGeometry()
        self.setMinimumSize(min(1080, available.width() - 48), min(720, available.height() - 64))
        self.resize(min(1440, available.width() - 48), min(940, available.height() - 64))
        self._window_preferences = QSettings("sirdimitry", "StopFrame")
        geometry = self._window_preferences.value("windowGeometry")
        if geometry:
            self.restoreGeometry(geometry)

        self.settings = load_settings()
        self.videos: list[VideoItem] = []
        self.capture_store = CaptureStore()

        self.settings_tab = SettingsTab(self.settings, self.videos, self.capture_store)
        self.timeline_tab = TimelineTab(self.videos, self.settings, self.capture_store)
        self.screenshots_tab = ScreenshotsTab(self.capture_store, self.settings)
        self.settings_tab.logos_changed.connect(self.screenshots_tab.refresh_logo_library)
        self.screenshots_tab.logo_settings_requested.connect(self.settings_tab.show_logo_settings)

        self.settings_tab.videos_changed.connect(self.timeline_tab.refresh)
        self.settings_tab.video_removed.connect(self.timeline_tab.remove_video)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.settings_tab, "1  ·  Видео")
        self.tabs.addTab(self.timeline_tab, "2  ·  Выбор вручную")
        self.tabs.addTab(self.screenshots_tab, "3  ·  Кадры и экспорт")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.timeline_tab.set_shortcuts_enabled(self.tabs.currentIndex() == TIMELINE_TAB_INDEX)

        self.export_button = QPushButton("Экспортировать кадры…")
        self.export_button.setObjectName("primaryButton")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self._on_export_clicked)
        self._export_worker: ExportWorker | None = None

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        header = QHBoxLayout()
        brand = QLabel("StopFrame")
        brand.setObjectName("appTitle")
        header.addWidget(brand)
        header.addStretch(1)
        privacy = QLabel("Видео остаются на вашем Mac")
        privacy.setProperty("class", "caption")
        header.addWidget(privacy)
        layout.addLayout(header)
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_hint = QLabel()
        self.page_hint.setProperty("class", "caption")
        self.page_hint.setWordWrap(True)
        layout.addWidget(self.page_title)
        layout.addWidget(self.page_hint)
        layout.addWidget(self.tabs, stretch=1)
        self.export_bar = QWidget()
        self.export_bar.setObjectName("workspaceToolbar")
        footer = QHBoxLayout(self.export_bar)
        footer.setContentsMargins(16, 12, 16, 12)
        self.export_summary = QLabel()
        self.export_summary.setWordWrap(True)
        footer.addWidget(self.export_summary, stretch=1)
        footer.addWidget(self.export_button)
        layout.addWidget(self.export_bar)
        self.screenshots_tab.review_changed.connect(self._update_export_state)
        self.capture_store.frame_added.connect(self._update_export_state)
        self.capture_store.video_removed.connect(self._update_export_state)
        self._on_tab_changed(self.tabs.currentIndex())
        self._update_export_state()
        self.setCentralWidget(central)

        self._build_menu()

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("Settings")
        logos_action = QAction("Logo Library…", self)
        logos_action.triggered.connect(self.settings_tab.show_logo_settings)
        settings_menu.addAction(logos_action)
        help_menu = self.menuBar().addMenu("Help")
        about_action = QAction("About StopFrame", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _on_tab_changed(self, index: int) -> None:
        log_ui_action(logger, "tab_switch", f"index={index}")
        self.timeline_tab.set_shortcuts_enabled(index == TIMELINE_TAB_INDEX)
        self._update_export_state()
        self.export_bar.setVisible(index == SCREENSHOTS_TAB_INDEX)
        titles = ("Найдите кадр, который стоит сохранить", "Выберите точный момент", "Подготовьте кадры к экспорту")
        hints = ("Добавьте видео и запустите автоматический отбор или перейдите к ручному выбору.",
                 "Выберите видео на ленте. ← → — по одному кадру, Space — сохранить кадр.",
                 "Выделите кадры для обработки. Двойной щелчок открывает детали и настройку логотипа.")
        self.page_title.setText(titles[index])
        self.page_hint.setText(hints[index])

    def _update_export_state(self, *_args) -> None:
        count = sum(frame.included for frame in self.capture_store.frames)
        busy = self._export_worker is not None
        self.export_button.setEnabled(bool(count) and not busy)
        self.export_button.setText("Экспортируем…" if busy else "Экспортировать кадры…")
        self.export_summary.setText(f"Кадров к экспорту: {count}  ·  {self.settings.export_format}" if count else "Сначала выберите кадры автоматически или на ленте видео.")
        self.export_button.setToolTip("Выбрать папку и сохранить кадры в исходном разрешении" if count else "Добавьте хотя бы один кадр для экспорта")

    def _on_export_clicked(self) -> None:
        if self._export_worker is not None:
            return
        included = [frame for frame in self.capture_store.frames if frame.included]
        log_ui_action(logger, "export_button", f"frames={len(included)}")
        if not included:
            QMessageBox.information(self, "Export", "No captured frames to export yet.")
            return

        if not self.settings.export_include_logo and not self._confirm_export_without_logo():
            return

        start_dir = self.settings.last_video_folder or ""
        dest_dir = QFileDialog.getExistingDirectory(self, "Choose Export Folder", start_dir)
        if not dest_dir:
            return

        self.export_button.setEnabled(False)
        progress_dialog = QProgressDialog("Exporting frames…", "Cancel", 0, len(included), self)
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)

        worker = ExportWorker(included, self.settings, Path(dest_dir))
        worker.progress.connect(progress_dialog.setValue)
        worker.finished_all.connect(lambda folders: self._on_export_finished(folders, progress_dialog))
        progress_dialog.canceled.connect(worker.request_cancel)
        self._export_worker = worker
        self._update_export_state()
        worker.start()

    def _confirm_export_without_logo(self) -> bool:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Экспорт без логотипа")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("Логотип выключен — кадры выйдут без автографа.\nЭкспортировать без логотипа?")
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        dialog.button(QMessageBox.StandardButton.Ok).setText("ОК")
        dialog.button(QMessageBox.StandardButton.Cancel).setText("Отменить")
        dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
        dialog.setEscapeButton(QMessageBox.StandardButton.Cancel)
        return dialog.exec() == QMessageBox.StandardButton.Ok

    def _on_export_finished(self, folders: list[str], progress_dialog: QProgressDialog) -> None:
        progress_dialog.close()
        self.export_button.setEnabled(True)
        worker = self._export_worker
        if worker is not None:
            worker.wait()
        self._export_worker = None
        self._update_export_state()
        if worker is not None and worker.failed_count:
            QMessageBox.warning(self, "Export", f"Could not export {worker.failed_count} frame(s). Check the destination folder and source files.")
        log_ui_action(logger, "export_finished", f"folders={len(folders)}")
        for folder in folders:
            subprocess.Popen(["open", folder])

    def closeEvent(self, event) -> None:
        self._window_preferences.setValue("windowGeometry", self.saveGeometry())
        self.settings_tab.shutdown()
        self.timeline_tab.shutdown()
        self.screenshots_tab.shutdown()
        if self._export_worker is not None:
            self._export_worker.wait()
        super().closeEvent(event)
