"""Generates the evenly-spaced thumbnail strip for a video's filmstrip."""

from __future__ import annotations

import cv2
import numpy as np

from stopframe.logging_setup import get_logger
from stopframe.core.performance import DECODER_THREADS

logger = get_logger("core.thumbnails")

THUMBNAIL_HEIGHT = 96


def generate_filmstrip_thumbnails(path: str, count: int) -> list[np.ndarray]:
    """Returns up to `count` BGR thumbnails, evenly spaced across the video's
    frames. Fewer come back if the file is short or partly unreadable."""
    capture = cv2.VideoCapture(path, cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_N_THREADS, DECODER_THREADS])
    if not capture.isOpened():
        capture.release()
        capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        capture.release()
        return []

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    thumbnails: list[np.ndarray] = []
    try:
        if frame_count <= 0:
            ok, frame = capture.read()
            if ok:
                thumbnails.append(_resize(frame))
            return thumbnails

        positions = [round(i * (frame_count - 1) / max(count - 1, 1)) for i in range(count)]
        for position in positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, position)
            ok, frame = capture.read()
            if ok:
                thumbnails.append(_resize(frame))
    finally:
        capture.release()
    return thumbnails


def _resize(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    if height <= 0:
        return frame
    scale = THUMBNAIL_HEIGHT / height
    new_width = max(1, round(width * scale))
    return cv2.resize(frame, (new_width, THUMBNAIL_HEIGHT), interpolation=cv2.INTER_AREA)
