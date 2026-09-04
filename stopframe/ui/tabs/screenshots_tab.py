"""Tab 3 — Screenshots: the review grid of captured frames.

Placeholder shell for now; the card grid, selection model, logo
side/aspect reassignment panel, and the HDR-source color-fix button land
in later phases.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ScreenshotsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("The captured-frame review grid goes here."))
        layout.addStretch(1)
