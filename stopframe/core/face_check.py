"""Local face quality: Apple Vision on Apple Silicon, MediaPipe fallback.

The native Swift helper uses supported Neural Engine compute stages on macOS
14+, and Vision's automatic scheduling on macOS 13. It ships inside the app;
source runs can build it with scripts/build_native.py. No model download or
Python ML initialization is needed for the native path.

Fallback face-quality check (eyes open / mouth closed) via MediaPipe's
legacy `solutions.face_mesh` API.

Note this is the *legacy* API (mediapipe==0.10.x, pinned in
requirements.txt), not the newer Tasks API (mediapipe>=1.0's
FaceLandmarker) — that one requires a model file fetched separately from
Google's model zoo (StopFrame never downloads anything) *and*, on this
machine, its GPU/Metal calculator init crashes the whole process with a
native C++ CHECK failure that Python can't catch. The legacy API ships
its model inside the pip wheel (no download needed) and, tested
repeatedly, doesn't hit that crash.

Detection runs in a subprocess (face_check_worker.py) rather than
in-process: a third-party native ML library is never trusted not to
crash on some future frame. That worker is long-lived — importing
mediapipe and constructing FaceMesh costs ~1s, so a fresh subprocess per
frame made auto-pick visibly slow on real footage (dozens of sampled
frames per video). One worker process is reused across an entire
auto-pick run instead, communicated with over stdin/stdout. If it
crashes or hangs, only that subprocess dies — this module treats it as
"no face found" and disables further attempts for the rest of the run,
same fallback the spec calls for when face-quality checking isn't
available.
"""

from __future__ import annotations

import json
import platform
import select
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import cv2

from stopframe.logging_setup import get_logger

logger = get_logger("core.face_check")

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_WORKER_TIMEOUT_SECONDS = 8.0
_WORKER_STARTUP_TIMEOUT_SECONDS = 30.0

_disabled = False
_availability_checked = False
_available = False
_worker: subprocess.Popen | None = None
_native_failed = False
_worker_backend = "mediapipe"
_compute_devices: dict[str, str] = {}


def native_worker_path() -> Path | None:
    if sys.platform != "darwin" or platform.machine() != "arm64" or _native_failed:
        return None
    from stopframe.resources import resource_path
    path = (resource_path("native", "StopFrameFaceWorker") if getattr(sys, "frozen", False)
            else _REPO_ROOT / "build" / "StopFrameFaceWorker")
    return path if path.is_file() else None


def backend_description() -> str:
    if _worker_backend == "appleVision":
        accelerator = "Neural Engine" if "neuralEngine" in _compute_devices.values() else "automatic compute"
        return f"Apple Vision ({accelerator})"
    return "MediaPipe (CPU)"


def _fallback_to_mediapipe() -> bool:
    global _native_failed, _availability_checked, _available
    if _worker_backend != "appleVision":
        return False
    logger.warning("Apple Vision unavailable; falling back to MediaPipe")
    shutdown()
    _native_failed = True
    _availability_checked = _available = False
    return True


@dataclass
class FaceQuality:
    face_found: bool
    eyes_open: bool = True
    mouth_closed: bool = True
    bbox: tuple[int, int, int, int] | None = None  # x, y, w, h in pixels


def is_available() -> bool:
    global _availability_checked, _available, _compute_devices
    if not _availability_checked:
        _availability_checked = True
        # Import and initialize native ML only in the isolated worker. Even an
        # availability import can stall for minutes in a frozen Qt application.
        worker = _ensure_worker()
        if worker is not None:
            try:
                worker.stdin.write(json.dumps({"cmd": "ping"}) + "\n")
                worker.stdin.flush()
                ready, _, _ = select.select([worker.stdout], [], [], _WORKER_STARTUP_TIMEOUT_SECONDS)
                response = json.loads(worker.stdout.readline()) if ready else {}
                _available = response.get("ready", False)
                _compute_devices = response.get("compute", {})
            except (OSError, ValueError):
                _available = False
        if not _available:
            if _fallback_to_mediapipe():
                return is_available()
            _disable("Face check worker initialization failed or timed out")
        else:
            logger.info("Face checks ready: %s", backend_description())
    return _available and not _disabled


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--face-worker"]
    return [sys.executable, "-m", "stopframe.core.face_check_worker"]


def _ensure_worker() -> subprocess.Popen | None:
    global _worker, _worker_backend
    if _worker is not None and _worker.poll() is None:
        return _worker
    try:
        native = native_worker_path()
        _worker_backend = "appleVision" if native else "mediapipe"
        _worker = subprocess.Popen(
            [str(native)] if native else worker_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=str(_REPO_ROOT),
        )
    except OSError as error:
        logger.error(f"Could not start face check worker: {error!r}")
        _worker = None
    return _worker


def _disable(reason: str) -> None:
    global _disabled
    logger.error(f"{reason} — disabling face-quality check for this run")
    _disabled = True
    shutdown()


def check_face_quality(frame_bgr: np.ndarray) -> FaceQuality:
    if not is_available():
        return FaceQuality(face_found=False)

    worker = _ensure_worker()
    if worker is None:
        if _fallback_to_mediapipe():
            return check_face_quality(frame_bgr)
        _disable("Face check worker could not be started")
        return FaceQuality(face_found=False)

    native = _worker_backend == "appleVision"
    with tempfile.NamedTemporaryFile(suffix=".png" if native else ".npy", delete=False) as handle:
        temp_path = handle.name

    try:
        if native:
            if not cv2.imwrite(temp_path, frame_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
                raise OSError("Could not write Vision input")
        else:
            np.save(temp_path, frame_bgr)
        worker.stdin.write(json.dumps({"frame_path": temp_path}) + "\n")
        worker.stdin.flush()

        ready, _, _ = select.select([worker.stdout], [], [], _WORKER_TIMEOUT_SECONDS)
        if not ready:
            if _fallback_to_mediapipe():
                return check_face_quality(frame_bgr)
            _disable("Face check worker timed out")
            return FaceQuality(face_found=False)

        line = worker.stdout.readline()
        if not line:
            if _fallback_to_mediapipe():
                return check_face_quality(frame_bgr)
            _disable(f"Face check worker exited (code {worker.poll()})")
            return FaceQuality(face_found=False)

        data = json.loads(line)
    except (OSError, ValueError, BrokenPipeError) as error:
        if _fallback_to_mediapipe():
            return check_face_quality(frame_bgr)
        _disable(f"Face check worker communication failed: {error!r}")
        return FaceQuality(face_found=False)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if "error" in data:
        if _fallback_to_mediapipe():
            return check_face_quality(frame_bgr)
        _disable(f"Face check worker reported an error: {data['error']}")
        return FaceQuality(face_found=False)

    bbox = tuple(data["bbox"]) if data.get("bbox") else None
    return FaceQuality(
        face_found=data.get("face_found", False),
        eyes_open=data.get("eyes_open", True),
        mouth_closed=data.get("mouth_closed", True),
        bbox=bbox,
    )


def shutdown() -> None:
    """Stops the persistent worker, if running. Safe to call any time —
    a fresh one is started lazily on the next check_face_quality() call
    (unless disabled after a crash)."""
    global _worker
    if _worker is None:
        return
    try:
        if _worker.poll() is None:
            try:
                _worker.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                _worker.stdin.flush()
                _worker.wait(timeout=2.0)
            except (OSError, subprocess.TimeoutExpired, BrokenPipeError):
                _worker.kill()
                _worker.wait()
    finally:
        _worker = None
