"""Renders one included capture at full resolution and writes it into a
"logo" subfolder of a destination the user picks at export time (defaults
to the folder the source videos were loaded from, but is asked every
export — see MainWindow._on_export_clicked). Filenames skip the source
video's own name (can be long/unwieldy) in favor of a VLC-style real
capture timestamp — date, time to the millisecond — plus the frame
number, so names stay short and are unique by construction; the prefix
is added before or after per the Settings toggle. A numeric suffix is
still appended defensively if a name ever collides with an existing file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from stopframe.config import Settings
from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate
from stopframe.logging_setup import get_logger

logger = get_logger("core.exporter")


def _capture_timestamp() -> str:
    """VLC-style: 2026-09-04-11h45m32s728 (date, time, milliseconds)."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d-%Hh%Mm%Ss") + f"{now.microsecond // 1000:03d}"


def build_export_filename(frame_index: int, prefix: str, prefix_before_name: bool, extension: str) -> str:
    stamped = f"{_capture_timestamp()}_frame{frame_index}"
    prefix = prefix.strip()
    if not prefix:
        name = stamped
    elif prefix_before_name:
        name = f"{prefix}-{stamped}"
    else:
        name = f"{stamped}-{prefix}"
    return f"{name}.{extension}"


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def export_frame(candidate: FrameCandidate, settings: Settings, dest_root: Path) -> Path | None:
    source = FrameSource(candidate.video_path)
    frame = source.read_at(candidate.timestamp_seconds)
    source.close()
    if frame is None:
        logger.error(
            f"Could not read frame for export: {Path(candidate.video_path).name} @ {candidate.timestamp_seconds:.2f}s"
        )
        return None

    if candidate.hdr_fix:
        frame = apply_hdr_fix(frame)

    image = frame_to_image(frame)
    slot = settings.logo_slots.get(candidate.logo_placement.slot_key)
    logo_path = slot.path if (slot and settings.export_include_logo) else None
    composed = compose_logo(image, logo_path, candidate.logo_placement)

    extension = "png" if settings.export_format == "PNG" else "jpg"
    filename = build_export_filename(
        candidate.frame_index,
        settings.export_prefix,
        settings.prefix_before_name,
        extension,
    )
    dest_dir = dest_root / "logo"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = _unique_path(dest_dir, filename)

    try:
        if settings.export_format == "PNG":
            composed.save(dest_path, format="PNG")
        else:
            composed.save(dest_path, format="JPEG", quality=settings.jpeg_quality, subsampling=0)
    except OSError as error:
        logger.error(f"Failed to write export file: {error!r}")
        return None

    return dest_path
