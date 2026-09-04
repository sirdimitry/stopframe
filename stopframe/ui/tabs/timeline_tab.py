"""Tab 2 — Timeline: per-video filmstrip, playhead, and manual capture.

Placeholder shell for now; the filmstrip widget, live logo-composited
preview, and capture shortcut land in a later phase.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TimelineTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Per-video filmstrip and manual frame capture go here."))
        layout.addStretch(1)
