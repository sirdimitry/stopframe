"""Shared plain-data types used across the UI and the processing core."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AspectRatio(str, Enum):
    RATIO_16_9 = "16:9"
    RATIO_4_3 = "4:3"
    OTHER = "other"


@dataclass
class VideoItem:
    path: str
    width: int
    height: int
    duration_seconds: float
    aspect_ratio: AspectRatio

    @property
    def file_name(self) -> str:
        from pathlib import Path

        return Path(self.path).name


class FrameOrigin(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class LogoPlacement:
    slot_key: str  # one of stopframe.config.LOGO_SLOT_KEYS
    offset_x: int
    offset_y: int
    scale: float


@dataclass
class FrameCandidate:
    video_path: str
    frame_index: int
    timestamp_seconds: float
    origin: FrameOrigin
    logo_placement: LogoPlacement
    included: bool = True
    sharpness_score: float = 0.0
