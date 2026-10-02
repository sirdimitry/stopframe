"""Lossless quarter-turn rotation shared by previews and full-size export."""
from __future__ import annotations

import numpy as np


def rotate_frame(frame: np.ndarray, clockwise_quarter_turns: int) -> np.ndarray:
    turns = clockwise_quarter_turns % 4
    if not turns:
        return frame
    return np.ascontiguousarray(np.rot90(frame, -turns))
