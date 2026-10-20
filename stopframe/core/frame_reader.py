"""Seeks into a video and reads a single frame at a timestamp.

FrameSource keeps one cv2.VideoCapture open so scrubbing the timeline
doesn't reopen the file on every mouse-move — the caller is expected to
open one per "currently active" video and close it when switching away.
Still images use Pillow and EXIF orientation, bypassing video capture.
"""

from __future__ import annotations

from typing import Optional
import sys
import subprocess

import cv2
import numpy as np

from stopframe.logging_setup import get_logger
from stopframe.core.performance import DECODER_THREADS
from stopframe.core.photo_source import is_photo_path, read_photo

logger = get_logger("core.frame_reader")


class FrameSource:
    def __init__(self, path: str, *, native_decode: bool = False, decoder_threads: int = DECODER_THREADS) -> None:
        self.path = path
        self._is_photo = is_photo_path(path)
        self._capture = None
        if self._is_photo:
            return
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
        if self._is_photo:
            from pathlib import Path
            return Path(self.path).is_file()
        return self._capture.isOpened()

    def read_at(self, timestamp_seconds: float) -> Optional[np.ndarray]:
        if self._is_photo:
            try:
                return read_photo(self.path)
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                logger.error("Could not read photo %s: %s", self.path, error)
                return None
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
        if self._capture is not None:
            self._capture.release()
