"""Shared collection of captured frames, decoupling the Timeline tab
(which produces manual captures) from the Screenshots tab (which reviews
everything, auto and manual alike) via a Qt signal."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from stopframe.core.models import FrameCandidate


class CaptureStore(QObject):
    frame_added = Signal(object)  # FrameCandidate

    def __init__(self) -> None:
        super().__init__()
        self.frames: list[FrameCandidate] = []

    def add(self, frame: FrameCandidate) -> None:
        self.frames.append(frame)
        self.frame_added.emit(frame)

    def markers_for(self, video_path: str) -> list[FrameCandidate]:
        return [f for f in self.frames if f.video_path == video_path and f.included]
