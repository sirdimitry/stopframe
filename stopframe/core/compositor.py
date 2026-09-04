"""Composites a logo onto a frame.

The single engine reused by both the live timeline preview and the final
export — what the preview shows is exactly what export writes to disk.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image

from stopframe.core.models import AspectRatio, LogoPlacement
from stopframe.logging_setup import get_logger

logger = get_logger("core.compositor")


def frame_to_image(frame_bgr: np.ndarray) -> Image.Image:
    """OpenCV decodes frames as BGR; Pillow works in RGB."""
    return Image.fromarray(frame_bgr[:, :, ::-1])


def compose_logo(frame: Image.Image, logo_path: Optional[str], placement: LogoPlacement) -> Image.Image:
    """Returns a new image with the logo composited on top — `frame` is never mutated."""
    result = frame.convert("RGB")
    if not logo_path:
        return result

    try:
        logo = Image.open(logo_path)
        logo.load()
        logo = logo.convert("RGBA")
    except (OSError, ValueError) as error:
        logger.error(f"Could not open logo file for slot {placement.slot_key}: {error!r}")
        return result

    scale = max(placement.scale, 0.01)
    new_size = (max(1, round(logo.width * scale)), max(1, round(logo.height * scale)))
    if new_size != logo.size:
        logo = logo.resize(new_size, Image.LANCZOS)

    if placement.slot_key.endswith("-right"):
        x = result.width - placement.offset_x - logo.width
    else:
        x = placement.offset_x
    y = placement.offset_y

    result.paste(logo, (x, y), logo)
    return result


def pick_slot_key(aspect_ratio: AspectRatio, side: str) -> str:
    """side is 'left' or 'right'. AspectRatio.OTHER falls back to the 16:9 slots."""
    base = "4:3" if aspect_ratio == AspectRatio.RATIO_4_3 else "16:9"
    return f"{base}-{side}"


def default_placement(slot_key: str, offset_x: int, offset_y: int, scale: float) -> LogoPlacement:
    return LogoPlacement(slot_key=slot_key, offset_x=offset_x, offset_y=offset_y, scale=scale)
