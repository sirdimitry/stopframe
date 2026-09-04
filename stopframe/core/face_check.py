"""Optional face-quality check (eyes open / mouth closed) via MediaPipe's
FaceLandmarker task.

Two layers of "never let this touch the app":

1. StopFrame never downloads anything — pip's mediapipe package doesn't
   bundle FaceLandmarker's model file (normally fetched from Google's
   model zoo at first use). This check activates only if a model file
   has been placed by hand at MODEL_PATH; otherwise it degrades to "no
   face found" with no error — the same fallback the spec calls for.

2. Even with a model present, MediaPipe's GPU/Metal calculator init can
   abort the whole process on some machines (a native C++ CHECK failure,
   not a catchable Python exception). So the actual detection runs in a
   short-lived subprocess (face_check_worker.py) — if it crashes or
   hangs, only that subprocess dies; this module treats it as "no face"
   and disables further attempts for the rest of the run.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from stopframe.logging_setup import get_logger

logger = get_logger("core.face_check")

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = _REPO_ROOT / "assets" / "face_landmarker.task"

_WORKER_TIMEOUT_SECONDS = 8.0

_disabled = False
_availability_logged = False


@dataclass
class FaceQuality:
    face_found: bool
    eyes_open: bool = True
    mouth_closed: bool = True
    bbox: tuple[int, int, int, int] | None = None  # x, y, w, h in pixels


def is_available() -> bool:
    global _availability_logged
    if not MODEL_PATH.exists():
        if not _availability_logged:
            _availability_logged = True
            logger.info("Face-quality check inactive: no local model at assets/face_landmarker.task")
        return False
    return not _disabled


def check_face_quality(frame_bgr: np.ndarray) -> FaceQuality:
    global _disabled
    if not is_available():
        return FaceQuality(face_found=False)

    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as handle:
        temp_path = handle.name

    try:
        np.save(temp_path, frame_bgr)
        result = subprocess.run(
            [sys.executable, "-m", "stopframe.core.face_check_worker", temp_path],
            capture_output=True,
            text=True,
            timeout=_WORKER_TIMEOUT_SECONDS,
            cwd=str(_REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        logger.error("Face check worker timed out — disabling face-quality check for this run")
        _disabled = True
        return FaceQuality(face_found=False)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if result.returncode != 0:
        logger.error(
            f"Face check worker exited abnormally (code {result.returncode}) — "
            "disabling face-quality check for this run"
        )
        _disabled = True
        return FaceQuality(face_found=False)

    try:
        last_line = result.stdout.strip().splitlines()[-1]
        data = json.loads(last_line)
    except (ValueError, IndexError) as error:
        logger.error(f"Face check worker returned unreadable output: {error!r}")
        _disabled = True
        return FaceQuality(face_found=False)

    if "error" in data:
        logger.error(f"Face check worker reported an error: {data['error']}")
        return FaceQuality(face_found=False)

    bbox = tuple(data["bbox"]) if data.get("bbox") else None
    return FaceQuality(
        face_found=data.get("face_found", False),
        eyes_open=data.get("eyes_open", True),
        mouth_closed=data.get("mouth_closed", True),
        bbox=bbox,
    )
