#!/usr/bin/env python3
"""StopFrame entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from stopframe.logging_setup import get_logger
from stopframe.ui.button_feedback import ButtonPressFeedback
from stopframe.ui.main_window import MainWindow

logger = get_logger("main")

THEME_PATH = Path(__file__).parent / "stopframe" / "ui" / "theme" / "dark_orange.qss"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("StopFrame")
    # Fusion so the QSS below renders identically instead of the native
    # macOS style partially overriding it (comboboxes, spinboxes especially).
    app.setStyle("Fusion")
    try:
        app.setStyleSheet(THEME_PATH.read_text(encoding="utf-8"))
    except OSError as error:
        logger.error(f"Could not load theme stylesheet: {error!r}")
    button_feedback = ButtonPressFeedback(app)
    app.installEventFilter(button_feedback)
    window = MainWindow()
    window.show()
    logger.info("StopFrame started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
