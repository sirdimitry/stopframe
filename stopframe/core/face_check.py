"""Optional face-quality check (eyes open / mouth closed) via MediaPipe's
FaceLandmarker task.

StopFrame never downloads anything — the pip `mediapipe` package does not
bundle FaceLandmarker's model file (a .task asset normally fetched from
Google's model zoo at first use), and fetching it ourselves would violate
the "nothing leaves or reaches this machine over the network" rule. So
this check activates only if someone has manually placed a model file at
MODEL_PATH; otherwise it degrades to "no face found" with no error, and
frames are scored on sharpness and composition alone — exactly the
fallback the spec calls for.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from stopframe.logging_setup import get_logger

logger = get_logger("core.face_check")

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "face_landmarker.task"

# 468-point FaceMesh topology indices: (top, bottom, outer corner, inner corner)
_LEFT_EYE = (386, 374, 263, 362)
_RIGHT_EYE = (159, 145, 33, 133)
# (upper lip, lower lip, left corner, right corner)
_MOUTH = (13, 14, 78, 308)

_EYE_OPEN_RATIO = 0.15
_MOUTH_CLOSED_RATIO = 0.15

_landmarker = None
_availability_logged = False


@dataclass
class FaceQuality:
    face_found: bool
    eyes_open: bool = True
    mouth_closed: bool = True
    bbox: tuple[int, int, int, int] | None = None  # x, y, w, h in pixels


def is_available() -> bool:
    global _availability_logged
    available = MODEL_PATH.exists()
    if not available and not _availability_logged:
        _availability_logged = True
        logger.info("Face-quality check inactive: no local model at assets/face_landmarker.task")
    return available


def _get_landmarker():
    global _landmarker
    if _landmarker is not None:
        return _landmarker
    try:
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions

        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
            num_faces=1,
        )
        _landmarker = vision.FaceLandmarker.create_from_options(options)
    except Exception as error:  # pragma: no cover - depends on local model/runtime
        logger.error(f"Could not initialize face landmarker: {error!r}")
        _landmarker = False
    return _landmarker


def check_face_quality(frame_bgr: np.ndarray) -> FaceQuality:
    if not is_available():
        return FaceQuality(face_found=False)
    landmarker = _get_landmarker()
    if not landmarker:
        return FaceQuality(face_found=False)

    import cv2
    import mediapipe as mp

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    try:
        result = landmarker.detect(mp_image)
    except Exception as error:  # pragma: no cover - depends on local model/runtime
        logger.error(f"Face landmark detection failed: {error!r}")
        return FaceQuality(face_found=False)

    if not result.face_landmarks:
        return FaceQuality(face_found=False)

    landmarks = result.face_landmarks[0]
    height, width = frame_bgr.shape[:2]
    xs = [point.x * width for point in landmarks]
    ys = [point.y * height for point in landmarks]
    bbox = (int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys)))

    return FaceQuality(
        face_found=True,
        eyes_open=_eyes_open(landmarks),
        mouth_closed=_mouth_closed(landmarks),
        bbox=bbox,
    )


def _distance(landmarks, a: int, b: int) -> float:
    return math.hypot(landmarks[a].x - landmarks[b].x, landmarks[a].y - landmarks[b].y)


def _eye_aspect_ratio(landmarks, top: int, bottom: int, outer: int, inner: int) -> float:
    horizontal = _distance(landmarks, outer, inner)
    return _distance(landmarks, top, bottom) / horizontal if horizontal > 0 else 0.0


def _eyes_open(landmarks) -> bool:
    left = _eye_aspect_ratio(landmarks, *_LEFT_EYE)
    right = _eye_aspect_ratio(landmarks, *_RIGHT_EYE)
    return ((left + right) / 2) > _EYE_OPEN_RATIO


def _mouth_closed(landmarks) -> bool:
    top, bottom, left, right = _MOUTH
    horizontal = _distance(landmarks, left, right)
    ratio = _distance(landmarks, top, bottom) / horizontal if horizontal > 0 else 0.0
    return ratio < _MOUTH_CLOSED_RATIO
