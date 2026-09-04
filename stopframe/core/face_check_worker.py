"""Standalone worker that runs one face-landmark check in isolation.

Uses MediaPipe's legacy `solutions.face_mesh` API — unlike the newer
Tasks API (mediapipe>=1.0's FaceLandmarker), this one doesn't require a
separately-downloaded model file (it ships inside the pip wheel) and,
on this machine, doesn't crash trying to init a Metal/GPU service. Still
run as a subprocess rather than in-process: a third-party native ML
library is never trusted not to crash on some future frame, and a crash
here should only take down this short-lived worker, never the main app.

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
    pa, pb = landmarks[a], landmarks[b]
    return math.hypot(pa.x - pb.x, pa.y - pb.y)


def _eye_aspect_ratio(landmarks, top: int, bottom: int, outer: int, inner: int) -> float:
    horizontal = _distance(landmarks, outer, inner)
    return _distance(landmarks, top, bottom) / horizontal if horizontal > 0 else 0.0


def main() -> None:
    frame_bgr = np.load(sys.argv[1])

    import mediapipe as mp

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=False,
    )
    rgb = frame_bgr[:, :, ::-1]
    result = face_mesh.process(rgb)
    face_mesh.close()

    if not result.multi_face_landmarks:
        print(json.dumps({"face_found": False}))
        return

    landmarks = result.multi_face_landmarks[0].landmark
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
