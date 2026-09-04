"""Auto-matches logo overlay PNGs to their slot from a single folder —
no manual per-slot assignment. Aspect and orientation come from each
PNG's own pixel dimensions (same long/short-side logic used for source
videos); left/right comes from keywords in the filename, since that
can't be read from the image itself.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from stopframe.config import build_slot_key
from stopframe.core.models import AspectRatio, Orientation
from stopframe.core.video_probe import classify_aspect_ratio
from stopframe.logging_setup import get_logger

logger = get_logger("core.logo_matcher")

_LEFT_KEYWORDS = ("слева", "лево", "left")
_RIGHT_KEYWORDS = ("справа", "право", "right")


def _side_from_filename(name: str) -> str | None:
    lowered = name.lower()
    is_left = any(keyword in lowered for keyword in _LEFT_KEYWORDS)
    is_right = any(keyword in lowered for keyword in _RIGHT_KEYWORDS)
    if is_left and not is_right:
        return "left"
    if is_right and not is_left:
        return "right"
    return None


def _aspect_from_text(text: str) -> AspectRatio | None:
    """A file named/folder-grouped like "...4на3.png" or living under a
    "4 на 3" folder is a deliberate aspect label — trust it over the PNG's
    own pixel ratio, which for these templates is often just "whatever
    resolution the source photo was" (e.g. a 3:2 camera export) rather
    than a literal 4:3 rectangle."""
    lowered = text.lower()
    if "16" in lowered and "9" in lowered:
        return AspectRatio.RATIO_16_9
    if "4" in lowered and "3" in lowered:
        return AspectRatio.RATIO_4_3
    return None


def _detect_aspect(path: Path, width: int, height: int) -> AspectRatio:
    hint = _aspect_from_text(f"{path.parent.name} {path.stem}")
    if hint is not None:
        return hint
    return classify_aspect_ratio(width, height)


def match_logos_in_folder(folder: str) -> dict[str, str]:
    """Returns {slot_key: file_path} for every confidently-matched PNG
    found under `folder` (recursive, sorted for deterministic results)."""
    matches: dict[str, str] = {}
    for path in sorted(Path(folder).rglob("*.png")):
        side = _side_from_filename(path.stem)
        if side is None:
            logger.info(f"Skipping logo (no left/right side in name): {path.name}")
            continue

        try:
            with Image.open(path) as image:
                width, height = image.size
        except OSError as error:
            logger.error(f"Could not read logo image {path.name}: {error!r}")
            continue

        aspect = _detect_aspect(path, width, height)
        if aspect == AspectRatio.OTHER:
            logger.info(f"Skipping logo (unrecognized aspect ratio {width}x{height}): {path.name}")
            continue

        orientation = Orientation.PORTRAIT.value if height > width else Orientation.LANDSCAPE.value
        slot_key = build_slot_key(aspect.value, orientation, side)

        if slot_key in matches:
            logger.info(
                f"Slot {slot_key} already matched to {Path(matches[slot_key]).name} — keeping it, ignoring {path.name}"
            )
            continue
        matches[slot_key] = str(path)

    return matches
