#!/usr/bin/env python3
"""Bumps the app version stored in VERSION.

Scheme: MAJOR.MINOR.PATCH
- PATCH increments by 1 on every bump, up to 20. On the step that would make
  it 21, it wraps to 0 and MINOR increments instead.
- MINOR increments up to 10. On the step that would make it 11, it wraps to
  0 and MAJOR increments instead.
- MAJOR has no ceiling.

Usage: python3 scripts/bump_version.py
"""

from pathlib import Path

MINOR_CEILING = 10
PATCH_CEILING = 20

VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def bump(major: int, minor: int, patch: int) -> tuple[int, int, int]:
    patch += 1
    if patch > PATCH_CEILING:
        patch = 0
        minor += 1
        if minor > MINOR_CEILING:
            minor = 0
            major += 1
    return major, minor, patch


def main() -> None:
    current = VERSION_FILE.read_text(encoding="utf-8").strip()
    major, minor, patch = (int(part) for part in current.split("."))
    new_version = "%d.%d.%d" % bump(major, minor, patch)
    VERSION_FILE.write_text(new_version + "\n", encoding="utf-8")
    print(f"{current} -> {new_version}")


if __name__ == "__main__":
    main()
