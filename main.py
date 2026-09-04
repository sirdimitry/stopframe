#!/usr/bin/env python3
"""StopFrame entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from stopframe.logging_setup import get_logger
from stopframe.ui.main_window import MainWindow

logger = get_logger("main")


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("StopFrame")
    window = MainWindow()
    window.show()
    logger.info("StopFrame started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
