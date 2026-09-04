"""Composites a logo overlay onto a frame.

The single engine reused by both the live timeline preview and the final
export — what the preview shows is exactly what export writes to disk.

Each slot holds a full-frame overlay PNG, pre-designed by hand to cover
the whole video frame at a given aspect/orientation/side (the logo mark is
already positioned inside it). So compositing is: fit the overlay to the
frame's exact pixel size, then alpha-composite it on top. offset_x/
offset_y/scale are a fine-tune nudge on top of that baseline, not the
primary positioning mechanism.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image

from stopframe.core.models import AspectRatio, LogoPlacement, Orientation
from stopframe.logging_setup import get_logger

logger = get_logger("core.compositor")


def frame_to_image(frame_bgr: np.ndarray) -> Image.Image:
    """OpenCV decodes frames as BGR; Pillow works in RGB."""
    return Image.fromarray(frame_bgr[:, :, ::-1])


def compose_logo(frame: Image.Image, logo_path: Optional[str], placement: LogoPlacement) -> Image.Image:
    """Returns a new image with the logo overlay composited on top — `frame` is never mutated."""
    base = frame.convert("RGBA")
    if not logo_path:
        return base.convert("RGB")

    try:
        overlay = Image.open(logo_path)
        overlay.load()
        overlay = overlay.convert("RGBA")
    except (OSError, ValueError) as error:
        logger.error(f"Could not open logo file for slot {placement.slot_key}: {error!r}")
        return base.convert("RGB")

    scale = max(placement.scale, 0.01)
    target_size = (max(1, round(base.width * scale)), max(1, round(base.height * scale)))
    if target_size != overlay.size:
        overlay = overlay.resize(target_size, Image.LANCZOS)

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(overlay, (placement.offset_x, placement.offset_y), overlay)

    return Image.alpha_composite(base, layer).convert("RGB")


def pick_slot_key(aspect_ratio: AspectRatio, orientation: Orientation, side: str) -> str:
    """side is 'left' or 'right'. AspectRatio.OTHER falls back to the 16:9 slots."""
    base = "4:3" if aspect_ratio == AspectRatio.RATIO_4_3 else "16:9"
    return f"{base}-{orientation.value}-{side}"


def default_placement(slot_key: str, offset_x: int = 0, offset_y: int = 0, scale: float = 1.0) -> LogoPlacement:
    return LogoPlacement(slot_key=slot_key, offset_x=offset_x, offset_y=offset_y, scale=scale)
