"""Shared plain-data types used across the UI and the processing core."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class AspectRatio(str, Enum):
    RATIO_16_9 = "16:9"
    RATIO_4_3 = "4:3"
    OTHER = "other"


class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


@dataclass
class VideoItem:
    path: str
    width: int
    height: int
    duration_seconds: float
    aspect_ratio: AspectRatio
    fps: float = 0.0

    @property
    def file_name(self) -> str:
        from pathlib import Path

        return Path(self.path).name

    @property
    def orientation(self) -> Orientation:
        return Orientation.PORTRAIT if self.height > self.width else Orientation.LANDSCAPE


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
    hdr_fix: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
