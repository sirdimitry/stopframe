"""A QGraphicsView with mouse-wheel and macOS trackpad-pinch zoom.

Zoom is expressed relative to the "fit the viewport" baseline (1x..8x), not
absolute image pixels, since this is a resizable preview, not a fixed-size
canvas. Trackpad pinch on macOS arrives as QNativeGestureEvent with type
ZoomNativeGesture — that is not the same thing as QPinchGesture (which is
for touchscreens) and Qt does not route it through wheelEvent, so it has to
be caught in viewportEvent instead.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QFrame, QGraphicsView

MIN_ZOOM = 1.0
MAX_ZOOM = 8.0
WHEEL_SENSITIVITY = 1000.0


class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._fit_scale = 1.0
        self._zoom = 1.0

    def fit_to_window(self, item_rect: QRectF) -> None:
        self.resetTransform()
        self._zoom = 1.0
        view_size = self.viewport().size()
        if item_rect.isEmpty() or item_rect.width() <= 0 or item_rect.height() <= 0:
            self._fit_scale = 1.0
            return
        scale = min(view_size.width() / item_rect.width(), view_size.height() / item_rect.height())
        scale = max(scale, 0.001)
        self.scale(scale, scale)
        self._fit_scale = scale
        self.centerOn(item_rect.center())

    def reset_zoom(self) -> None:
        scene = self.scene()
        if scene is not None:
            self.fit_to_window(scene.sceneRect())

    def _apply_zoom(self, factor: float) -> None:
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._zoom * factor))
        if new_zoom == self._zoom:
            return
        applied_factor = new_zoom / self._zoom
        self._zoom = new_zoom
        self.scale(applied_factor, applied_factor)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta == 0:
            super().wheelEvent(event)
            return
        self._apply_zoom(1.0 + delta / WHEEL_SENSITIVITY)
        event.accept()

    def viewportEvent(self, event) -> bool:
        if (
            event.type() == QEvent.Type.NativeGesture
            and event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture
        ):
            self._apply_zoom(1.0 + event.value())
            return True
        return super().viewportEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.reset_zoom()
        super().mouseDoubleClickEvent(event)
