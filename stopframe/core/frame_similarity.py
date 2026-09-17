"""Small spatial fingerprints for conservative near-duplicate suppression.

Unlike a color histogram, these retain where details occur in the image.
Only small arrays are kept, never full-resolution sampled frames.
"""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class FrameFingerprint:
    gray: np.ndarray
    color: np.ndarray
    phash: np.ndarray


def fingerprint(frame: np.ndarray) -> FrameFingerprint:
    small = cv2.resize(frame, (64, 64), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    reduced = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    coefficients = cv2.dct(reduced.astype(np.float32))[:8, :8].flatten()[1:]
    return FrameFingerprint(gray, cv2.resize(small, (16, 16), interpolation=cv2.INTER_AREA),
                            coefficients > np.median(coefficients))


def are_similar(a: FrameFingerprint, b: FrameFingerprint) -> bool:
    # Local structural similarity, so movement in one part of a frame matters.
    x, y = a.gray.astype(np.float32), b.gray.astype(np.float32)
    blur = lambda image: cv2.GaussianBlur(image, (7, 7), 1.5)
    mx, my = blur(x), blur(y)
    vx, vy = blur(x * x) - mx * mx, blur(y * y) - my * my
    covariance = blur(x * y) - mx * my
    ssim = np.mean(((2 * mx * my + 6.5025) * (2 * covariance + 58.5225)) /
                   ((mx * mx + my * my + 6.5025) * (vx + vy + 58.5225)))
    color_delta = np.mean(np.abs(a.color.astype(np.float32) - b.color.astype(np.float32))) / 255
    # Allow small exposure/noise changes, but require spatial agreement too.
    centered_delta = np.mean(np.abs((x - x.mean()) - (y - y.mean()))) / 255
    hash_distance = np.count_nonzero(a.phash != b.phash)
    return bool(color_delta <= 0.08 and (ssim >= 0.94 or
                (hash_distance <= 6 and centered_delta <= 0.04)))
