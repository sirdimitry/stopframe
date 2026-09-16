"""Shared inertial-scroll setup for the app's QScrollArea instances.

QScroller only adds momentum/drag-to-pan on top of a gesture; plain wheel
and trackpad-swipe scrolling already go through QAbstractScrollArea's own
delta handling, so grabbing the gesture doesn't replace that path.
"""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractScrollArea, QScroller

PIXEL_SCROLL_STEP = 24


def enable_inertial_scroll(scroll_area: QAbstractScrollArea) -> None:
    QScroller.grabGesture(scroll_area.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
    scroll_area.verticalScrollBar().setSingleStep(PIXEL_SCROLL_STEP)
