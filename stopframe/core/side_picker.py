"""Picks which side (left/right) is less "busy" for the logo, per the
spec: split the frame into left/right thirds, measure edge density in
each, and prefer the calmer side — with a detected face counting heavily
against whichever side it's on."""

from __future__ import annotations

import cv2
import numpy as np

from stopframe.core.face_check import FaceQuality

_FACE_PENALTY = 1.0


def _edge_density(region_gray: np.ndarray) -> float:
    if region_gray.size == 0:
        return 0.0
    edges = cv2.Canny(region_gray, 80, 160)
    return float(np.count_nonzero(edges)) / edges.size


def pick_side(frame_bgr: np.ndarray, face: FaceQuality | None = None) -> str:
    height, width = frame_bgr.shape[:2]
    third = width // 3
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    left_busyness = _edge_density(gray[:, :third])
    right_busyness = _edge_density(gray[:, width - third:])

    if face is not None and face.face_found and face.bbox is not None:
        face_center_x = face.bbox[0] + face.bbox[2] / 2
        if face_center_x < third:
            left_busyness += _FACE_PENALTY
        elif face_center_x > width - third:
            right_busyness += _FACE_PENALTY

    return "left" if left_busyness <= right_busyness else "right"
