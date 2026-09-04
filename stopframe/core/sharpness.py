"""Blur detection via the variance of the Laplacian — a sharp frame has a
wide spread of edge response, a blurred one doesn't."""

from __future__ import annotations

import cv2
import numpy as np


def laplacian_variance(frame_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
