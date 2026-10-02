#!/usr/bin/env python3
"""StopFrame entry point."""

from __future__ import annotations

import sys

def main() -> None:
    # Dispatch before importing Qt or the main window: a bundled helper must
    # never create a second GUI (sys.executable is the .app executable).
    if "--face-worker" in sys.argv:
        from stopframe.core.face_check_worker import main as face_main
        face_main()
        return
    if "--version" in sys.argv:
        from stopframe import __version__
        print(__version__)
        return
    if "--self-test" in sys.argv:
        from stopframe.self_test import run
        run()
        return

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from stopframe import __version__
    from stopframe.logging_setup import get_logger
    from stopframe.resources import resource_path
    from stopframe.ui.button_feedback import ButtonPressFeedback
    from stopframe.ui.main_window import MainWindow
    from stopframe.core.performance import configure_threads
    configure_threads()
    logger = get_logger("main")
    theme_path = resource_path("stopframe", "ui", "theme", "dark_orange.qss")
    app = QApplication(sys.argv)
    app.setApplicationName("StopFrame")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(resource_path("assets", "branding", "app-icon.png"))))
    # Fusion so the QSS below renders identically instead of the native
    # macOS style partially overriding it (comboboxes, spinboxes especially).
    app.setStyle("Fusion")
    try:
        app.setStyleSheet(theme_path.read_text(encoding="utf-8"))
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
