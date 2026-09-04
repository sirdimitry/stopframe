"""Long-lived face-landmark check worker, run as a subprocess.

Uses MediaPipe's legacy `solutions.face_mesh` API — unlike the newer
Tasks API (mediapipe>=1.0's FaceLandmarker), this one doesn't require a
separately-downloaded model file (it ships inside the pip wheel) and,
on this machine, doesn't crash trying to init a Metal/GPU service.

Still isolated in a subprocess rather than run in-process: a third-party
native ML library is never trusted not to crash on some future frame,
and a crash here should only take down this worker, never the main app.
But importing mediapipe and constructing FaceMesh is the expensive part
(~1s), so unlike a one-shot-per-frame subprocess, this one stays alive
and handles a whole batch of frames — pays that cost once, not per frame.

Protocol: one JSON object per line on stdin, one JSON object per line of
response on stdout, flushed after each. `{"frame_path": "<npy file>"}` ->
`{"face_found": true, "eyes_open": ..., "mouth_closed": ..., "bbox": [...]}`
or `{"face_found": false}`. `{"cmd": "quit"}` (or stdin closing) exits.
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


def _check_one(face_mesh, frame_path: str) -> dict:
    frame_bgr = np.load(frame_path)
    rgb = frame_bgr[:, :, ::-1]
    result = face_mesh.process(rgb)

    if not result.multi_face_landmarks:
        return {"face_found": False}

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

    return {"face_found": True, "eyes_open": eyes_open, "mouth_closed": mouth_closed, "bbox": bbox}


def main() -> None:
    import mediapipe as mp

    face_mesh = mp.solutions.face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=False,
    )
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except ValueError as error:
                print(json.dumps({"error": repr(error)}), flush=True)
                continue
            if request.get("cmd") == "quit":
                break
            try:
                response = _check_one(face_mesh, request["frame_path"])
            except Exception as error:  # noqa: BLE001 - keep serving the next request
                response = {"error": repr(error)}
            print(json.dumps(response), flush=True)
    finally:
        face_mesh.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - deliberately broad, this is a subprocess boundary
        print(json.dumps({"error": repr(error)}), flush=True)
        sys.exit(1)
