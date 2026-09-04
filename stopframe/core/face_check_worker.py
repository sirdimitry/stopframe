"""Standalone worker that runs one face-landmark check in isolation.

MediaPipe's FaceLandmarker task can abort the whole process on some
machines/environments (a native C++ CHECK failure inside its GPU/Metal
calculator init — not a catchable Python exception). Running the check
here means a crash only takes down this short-lived worker; the caller
(face_check.py) spawns it per-frame via subprocess and treats a nonzero
exit or timeout as "no face found", never letting it touch the main app.

Usage: python3 -m stopframe.core.face_check_worker <frame.npy>
Prints one JSON line to stdout on success, e.g.:
  {"face_found": true, "eyes_open": true, "mouth_closed": true, "bbox": [x,y,w,h]}
  {"face_found": false}
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np

_LEFT_EYE = (386, 374, 263, 362)
_RIGHT_EYE = (159, 145, 33, 133)
_MOUTH = (13, 14, 78, 308)
_EYE_OPEN_RATIO = 0.15
_MOUTH_CLOSED_RATIO = 0.15


def _distance(landmarks, a: int, b: int) -> float:
    return math.hypot(landmarks[a].x - landmarks[b].x, landmarks[a].y - landmarks[b].y)


def _eye_aspect_ratio(landmarks, top: int, bottom: int, outer: int, inner: int) -> float:
    horizontal = _distance(landmarks, outer, inner)
    return _distance(landmarks, top, bottom) / horizontal if horizontal > 0 else 0.0


def main() -> None:
    from stopframe.core.face_check import MODEL_PATH

    frame_bgr = np.load(sys.argv[1])

    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH), delegate=BaseOptions.Delegate.CPU),
        num_faces=1,
    )
    landmarker = vision.FaceLandmarker.create_from_options(options)

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)

    if not result.face_landmarks:
        print(json.dumps({"face_found": False}))
        return

    landmarks = result.face_landmarks[0]
    height, width = frame_bgr.shape[:2]
    xs = [point.x * width for point in landmarks]
    ys = [point.y * height for point in landmarks]
    bbox = [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))]

    left = _eye_aspect_ratio(landmarks, *_LEFT_EYE)
    right = _eye_aspect_ratio(landmarks, *_RIGHT_EYE)
    eyes_open = ((left + right) / 2) > _EYE_OPEN_RATIO

    top, bottom, mouth_left, mouth_right = _MOUTH
    mouth_width = _distance(landmarks, mouth_left, mouth_right)
    mouth_ratio = _distance(landmarks, top, bottom) / mouth_width if mouth_width > 0 else 0.0
    mouth_closed = mouth_ratio < _MOUTH_CLOSED_RATIO

    print(json.dumps({"face_found": True, "eyes_open": eyes_open, "mouth_closed": mouth_closed, "bbox": bbox}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - deliberately broad, this is a subprocess boundary
        print(json.dumps({"error": repr(error)}))
        sys.exit(1)
