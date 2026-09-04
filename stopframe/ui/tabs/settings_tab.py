"""Tab 1 — Setup: source videos, logo slots, export prefix.

Placeholder shell for now; source loading, logo slot editors, and the
"run auto pick" trigger land in later phases.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SettingsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Source videos, logo slots, and export prefix go here."))
        layout.addStretch(1)
