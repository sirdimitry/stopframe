"""Bounded workloads: leave CPU capacity and memory for the UI and macOS."""
from __future__ import annotations

import os
import cv2
import numpy as np

ANALYSIS_MAX_EDGE = 960
PREVIEW_MAX_EDGE = 640
RENDER_CONCURRENCY = 2
EXPORT_CONCURRENCY = 2
DECODER_THREADS = min(4, max(1, (os.cpu_count() or 4) // 3))


def configure_threads() -> None:
    # Decoder/Qt workers already run in parallel. Giving each small operation
    # every CPU core oversubscribes the machine.
    # GCD doesn't support setting its queue width. Zero explicitly disables
    # OpenCV's inner parallelism; independent decoder/render jobs run in parallel.
    cv2.setNumThreads(0)


def bounded_frame(frame: np.ndarray, max_edge: int) -> np.ndarray:
    height, width = frame.shape[:2]
    scale = min(1.0, max_edge / max(height, width))
    if scale == 1:
        return frame
    return cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                      interpolation=cv2.INTER_AREA)
