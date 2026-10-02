"""Seeks into a video and reads a single frame at a timestamp.

FrameSource keeps one cv2.VideoCapture open so scrubbing the timeline
doesn't reopen the file on every mouse-move — the caller is expected to
open one per "currently active" video and close it when switching away.
"""

from __future__ import annotations

from typing import Optional
import sys

import cv2
import numpy as np

from stopframe.logging_setup import get_logger
from stopframe.core.performance import DECODER_THREADS

logger = get_logger("core.frame_reader")


class FrameSource:
    def __init__(self, path: str, *, native_decode: bool = False, decoder_threads: int = DECODER_THREADS) -> None:
        self.path = path
        self._decoder_threads = decoder_threads
        self._native_decode = native_decode and sys.platform == "darwin"
        # AVFoundation uses macOS's native media pipeline for analysis. Keep
        # preview/export on the same decoder to preserve their color match.
        if native_decode and sys.platform == "darwin":
            self._capture = cv2.VideoCapture(path, cv2.CAP_AVFOUNDATION)
            if not self._capture.isOpened():
                self._capture.release()
                self._capture = self._open_legacy()
                self._native_decode = False
        else:
            self._capture = self._open_legacy()

    def _open_legacy(self):
        if self._decoder_threads > 0:
            capture = cv2.VideoCapture(self.path, cv2.CAP_FFMPEG,
                                      [cv2.CAP_PROP_N_THREADS, self._decoder_threads])
            if capture.isOpened():
                return capture
            capture.release()
        return cv2.VideoCapture(self.path)

    def is_open(self) -> bool:
        return self._capture.isOpened()

    def read_at(self, timestamp_seconds: float) -> Optional[np.ndarray]:
        if not self._capture.isOpened():
            return None
        timestamp_ms = max(0.0, timestamp_seconds) * 1000
        seek_ok = self._capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
        ok, frame = self._capture.read()
        if self._native_decode and (not seek_ok or not ok):
            self._capture.release()
            self._capture = self._open_legacy()
            self._native_decode = False
            self._capture.set(cv2.CAP_PROP_POS_MSEC, timestamp_ms)
            ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        self._capture.release()
