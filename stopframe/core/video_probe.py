"""Reads a video file's metadata (resolution, duration, aspect ratio).

Metadata only — no frames are decoded here, so this is cheap enough to run
synchronously while the user is browsing for source files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2

from stopframe.core.models import AspectRatio, VideoItem
from stopframe.core.photo_source import PHOTO_EXTENSIONS, photo_size
import subprocess
from stopframe.logging_setup import get_logger

logger = get_logger("core.video_probe")

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}

_ASPECT_TOLERANCE = 0.05


def classify_aspect_ratio(width: int, height: int) -> AspectRatio:
    """Classifies by the long/short side ratio, independent of orientation —
    a 1080x1920 portrait clip is still "16:9" family, just rotated."""
    if width <= 0 or height <= 0:
        return AspectRatio.OTHER
    long_side, short_side = max(width, height), min(width, height)
    ratio = long_side / short_side
    if abs(ratio - 16 / 9) <= _ASPECT_TOLERANCE:
        return AspectRatio.RATIO_16_9
    if abs(ratio - 4 / 3) <= _ASPECT_TOLERANCE:
        return AspectRatio.RATIO_4_3
    return AspectRatio.OTHER


def probe_video(path: str) -> Optional[VideoItem]:
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        logger.error(f"Could not open video: {Path(path).name}")
        capture.release()
        return None
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        duration = frame_count / fps if fps > 0 else 0.0
    finally:
        capture.release()

    if width <= 0 or height <= 0:
        logger.error(f"Video has no readable frames: {Path(path).name}")
        return None

    return VideoItem(
        path=path,
        width=width,
        height=height,
        duration_seconds=duration,
        aspect_ratio=classify_aspect_ratio(width, height),
        fps=fps,
    )


def find_videos_in_folder(folder: str) -> list[str]:
    root = Path(folder)
    return sorted(
        str(p) for p in root.rglob("*") if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file()
    )


def probe_photo(path: str) -> Optional[VideoItem]:
    try:
        width, height = photo_size(path)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logger.error("Could not open photo %s: %s", Path(path).name, error)
        return None
    # Photos outside the 16:9 family always use 4:3 templates.
    aspect = classify_aspect_ratio(width, height)
    if aspect != AspectRatio.RATIO_16_9:
        aspect = AspectRatio.RATIO_4_3
    return VideoItem(path, width, height, 0, aspect, is_photo=True)


def find_media_in_folder(folder: str) -> list[str]:
    extensions = VIDEO_EXTENSIONS | PHOTO_EXTENSIONS
    return sorted(str(p) for p in Path(folder).rglob('*')
                  if p.is_file() and p.suffix.lower() in extensions)
