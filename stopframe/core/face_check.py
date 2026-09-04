"""Optional face-quality check (eyes open / mouth closed) via MediaPipe's
legacy `solutions.face_mesh` API.

Note this is the *legacy* API (mediapipe==0.10.x, pinned in
requirements.txt), not the newer Tasks API (mediapipe>=1.0's
FaceLandmarker) — that one requires a model file fetched separately from
Google's model zoo (StopFrame never downloads anything) *and*, on this
machine, its GPU/Metal calculator init crashes the whole process with a
native C++ CHECK failure that Python can't catch. The legacy API ships
its model inside the pip wheel (no download needed) and, tested
repeatedly, doesn't hit that crash.

Even so, detection still runs in a short-lived subprocess
(face_check_worker.py) rather than in-process: a third-party native ML
library is never trusted not to crash on some future frame. If it
crashes or hangs, only that subprocess dies — this module treats it as
"no face found" and disables further attempts for the rest of the run,
same fallback the spec calls for when face-quality checking isn't
available.
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

_WORKER_TIMEOUT_SECONDS = 8.0

_disabled = False
_availability_checked = False
_available = False


@dataclass
class FaceQuality:
    face_found: bool
    eyes_open: bool = True
    mouth_closed: bool = True
    bbox: tuple[int, int, int, int] | None = None  # x, y, w, h in pixels


def is_available() -> bool:
    global _availability_checked, _available
    if not _availability_checked:
        _availability_checked = True
        try:
            import mediapipe as mp

            _available = hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh")
            if not _available:
                logger.info("Face-quality check inactive: mediapipe.solutions.face_mesh not found")
        except ImportError:
            logger.info("Face-quality check inactive: mediapipe not installed")
            _available = False
    return _available and not _disabled


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
