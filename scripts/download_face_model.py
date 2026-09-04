#!/usr/bin/env python3
"""Fetches the MediaPipe FaceLandmarker model file used by the optional
eyes-open/mouth-closed check (see stopframe/core/face_check.py).

This is a deliberate, one-off, manually-triggered download — StopFrame
itself never contacts the network. Run this by hand for local dev/testing,
and again as an explicit step of the build/packaging process (once that
exists) so the shipped .app carries its own copy of the model instead of
fetching anything at runtime.

Usage: python3 scripts/download_face_model.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
EXPECTED_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"

DEST_PATH = Path(__file__).resolve().parent.parent / "assets" / "face_landmarker.task"


def main() -> None:
    DEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_URL}")
    urllib.request.urlretrieve(MODEL_URL, DEST_PATH)

    digest = hashlib.sha256(DEST_PATH.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        print(f"Checksum mismatch: got {digest}, expected {EXPECTED_SHA256}", file=sys.stderr)
        DEST_PATH.unlink(missing_ok=True)
        sys.exit(1)

    print(f"Saved to {DEST_PATH} ({DEST_PATH.stat().st_size} bytes, checksum verified)")


if __name__ == "__main__":
    main()
