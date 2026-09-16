"""App-wide tactile press feedback for every QPushButton.

Qt Style Sheets have no `transition` — hover/pressed state changes in
dark_orange.qss are instant. This adds a short opacity dip on press and a
spring-back on release via one QApplication-level event filter, so every
button (primaryButton, iconButton, plain) gets it automatically instead of
patching each button's construction site.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton

PRESS_OPACITY = 0.85
PRESS_DURATION_MS = 90
RELEASE_DURATION_MS = 120


class ButtonPressFeedback(QObject):
    """Install once: ``app.installEventFilter(ButtonPressFeedback(app))``."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._animations: dict[int, QPropertyAnimation] = {}

    def eventFilter(self, watched, event) -> bool:
        event_type = event.type()
        if isinstance(watched, QPushButton) and watched.isEnabled():
            if event_type == QEvent.Type.MouseButtonPress:
                self._animate(watched, PRESS_OPACITY, PRESS_DURATION_MS)
            elif event_type == QEvent.Type.MouseButtonRelease:
                self._animate(watched, 1.0, RELEASE_DURATION_MS)
        return False

    def _animate(self, button: QPushButton, target: float, duration_ms: int) -> None:
        effect = button.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(button)
            effect.setOpacity(1.0)
            button.setGraphicsEffect(effect)

        previous = self._animations.get(id(button))
        if previous is not None:
            previous.stop()

        animation = QPropertyAnimation(effect, b"opacity", button)
        animation.setDuration(duration_ms)
        animation.setStartValue(effect.opacity())
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        self._animations[id(button)] = animation
