"""Top-level window: three tabs plus a persistent Export button.

The Export button lives outside the QTabWidget so it stays visible and
clickable no matter which tab is active — it is the one action that always
applies to the whole session, not to a single tab.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget

from stopframe import __version__
from stopframe.config import load_settings
from stopframe.logging_setup import get_logger, log_ui_action
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
from stopframe.ui.tabs.settings_tab import SettingsTab
from stopframe.ui.tabs.timeline_tab import TimelineTab

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"StopFrame {__version__}")
        self.resize(1200, 800)

        self.settings = load_settings()
        self.settings_tab = SettingsTab(self.settings)
        self.timeline_tab = TimelineTab()
        self.screenshots_tab = ScreenshotsTab()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.settings_tab, "1. Setup")
        self.tabs.addTab(self.timeline_tab, "2. Timeline")
        self.tabs.addTab(self.screenshots_tab, "3. Screenshots")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.export_button = QPushButton("Export")
        self.export_button.setMinimumHeight(40)
        self.export_button.clicked.connect(self._on_export_clicked)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.tabs, stretch=1)
        layout.addWidget(self.export_button)
        self.setCentralWidget(central)

    def _on_tab_changed(self, index: int) -> None:
        log_ui_action(logger, "tab_switch", f"index={index}")

    def _on_export_clicked(self) -> None:
        log_ui_action(logger, "export_button")
        logger.info("Export requested but not yet implemented")
