"""Disk cache for a video's filmstrip thumbnails, so reopening the same
video doesn't re-decode it. Keyed on the source file's path, size, and
mtime — the cache is invalidated automatically if the file changes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np

from stopframe.logging_setup import get_logger
from stopframe.paths import thumbnail_cache_dir

logger = get_logger("core.thumbnail_cache")


def _cache_key(video_path: str, count: int) -> str:
    try:
        stat = Path(video_path).stat()
        fingerprint = f"{video_path}|{stat.st_size}|{stat.st_mtime_ns}|{count}"
    except OSError:
        fingerprint = f"{video_path}|{count}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _cache_file(video_path: str, count: int) -> Path:
    return thumbnail_cache_dir() / f"{_cache_key(video_path, count)}.npy"


def load_cached_thumbnails(video_path: str, count: int) -> Optional[list[np.ndarray]]:
    path = _cache_file(video_path, count)
    if not path.exists():
        return None
    try:
        stacked = np.load(path)
    except (OSError, ValueError) as error:
        logger.error(f"Could not read thumbnail cache, regenerating: {error!r}")
        return None
    return [frame for frame in stacked]


def save_thumbnails_to_cache(video_path: str, count: int, thumbnails: list[np.ndarray]) -> None:
    if not thumbnails or any(t.shape != thumbnails[0].shape for t in thumbnails):
        return  # mixed shapes shouldn't happen (fixed strip height), but stacking requires uniformity
    path = _cache_file(video_path, count)
    try:
        np.save(path, np.stack(thumbnails))
    except OSError as error:
        logger.error(f"Could not write thumbnail cache: {error!r}")
