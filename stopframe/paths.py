"""Local, per-user storage locations. Nothing here ever leaves the machine."""

from pathlib import Path

APP_NAME = "StopFrame"


def app_support_dir() -> Path:
    path = Path.home() / "Library" / "Application Support" / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return app_support_dir() / "settings.json"


def log_file() -> Path:
    return app_support_dir() / "stopframe.log"


def thumbnail_cache_dir() -> Path:
    path = app_support_dir() / "thumbnail_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
