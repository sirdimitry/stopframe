"""Reads the app version from the VERSION file at the repo root.

Version scheme is X.Y.Z where Y wraps at 10 (bumping X) and Z wraps at 20
(bumping Y) — see scripts/bump_version.py for the bump logic itself.
"""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_version() -> str:
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


__version__ = get_version()
