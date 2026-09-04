"""Seeks into a video and reads a single frame at a timestamp.

FrameSource keeps one cv2.VideoCapture open so scrubbing the timeline
doesn't reopen the file on every mouse-move — the caller is expected to
open one per "currently active" video and close it when switching away.
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from stopframe.logging_setup import get_logger

logger = get_logger("core.frame_reader")


class FrameSource:
    def __init__(self, path: str) -> None:
        self.path = path
        self._capture = cv2.VideoCapture(path)

    def is_open(self) -> bool:
        return self._capture.isOpened()

    def read_at(self, timestamp_seconds: float) -> Optional[np.ndarray]:
        if not self._capture.isOpened():
            return None
        self._capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, timestamp_seconds) * 1000)
        ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        self._capture.release()
