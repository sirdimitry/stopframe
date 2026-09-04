"""Renders one included capture at full resolution and writes it next to
its source video — the actual export step. Filenames combine the source
video's name, the frame's timestamp, and the configured prefix; a numeric
suffix is appended if that would collide with an existing file.
"""

from __future__ import annotations

from pathlib import Path

from stopframe.config import Settings
from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate
from stopframe.logging_setup import get_logger

logger = get_logger("core.exporter")


def build_export_filename(
    video_path: str, timestamp_seconds: float, prefix: str, prefix_before_name: bool, extension: str
) -> str:
    base = Path(video_path).stem
    stamped = f"{base}_{timestamp_seconds:.2f}s"
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


def export_frame(candidate: FrameCandidate, settings: Settings) -> Path | None:
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
    logo_path = slot.path if slot else None
    composed = compose_logo(image, logo_path, candidate.logo_placement)

    extension = "png" if settings.export_format == "PNG" else "jpg"
    filename = build_export_filename(
        candidate.video_path,
        candidate.timestamp_seconds,
        settings.export_prefix,
        settings.prefix_before_name,
        extension,
    )
    dest_dir = Path(candidate.video_path).parent
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
