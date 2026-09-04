"""Persisted user settings — local JSON file only, never transmitted anywhere.

Stores: the 4 logo slot files + their position/scale, the export prefix and
its order (before/after the file name), and the last folder videos were
loaded from.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from stopframe.logging_setup import get_logger
from stopframe.paths import settings_file

logger = get_logger("config")

LOGO_SLOT_KEYS = (
    "16:9-landscape-left",
    "16:9-landscape-right",
    "16:9-portrait-left",
    "16:9-portrait-right",
    "4:3-landscape-left",
    "4:3-landscape-right",
    "4:3-portrait-left",
    "4:3-portrait-right",
)


def parse_slot_key(slot_key: str) -> tuple[str, str, str]:
    """"4:3-portrait-left" -> ("4:3", "portrait", "left")."""
    aspect, orientation, side = slot_key.split("-")
    return aspect, orientation, side


def build_slot_key(aspect: str, orientation: str, side: str) -> str:
    return f"{aspect}-{orientation}-{side}"


@dataclass
class LogoSlot:
    """A slot holds a full-frame overlay PNG, pre-designed to cover the
    whole video frame at the slot's aspect/orientation/side — not a small
    movable sprite. offset_x/offset_y/scale are a fine-tune nudge on top
    of that baseline (0, 0, 1.0 = overlay exactly fills the frame as
    designed)."""

    path: Optional[str] = None
    offset_x: int = 0
    offset_y: int = 0
    scale: float = 1.0


@dataclass
class Settings:
    logo_slots: dict[str, LogoSlot] = field(
        default_factory=lambda: {key: LogoSlot() for key in LOGO_SLOT_KEYS}
    )
    export_prefix: str = ""
    prefix_before_name: bool = True
    last_video_folder: Optional[str] = None
    export_format: str = "PNG"  # "PNG" or "JPEG"
    jpeg_quality: int = 95

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    @staticmethod
    def from_dict(data: dict) -> "Settings":
        settings = Settings()
        slots = data.get("logo_slots", {})
        for key in LOGO_SLOT_KEYS:
            slot_data = slots.get(key)
            if slot_data:
                settings.logo_slots[key] = LogoSlot(**slot_data)
        settings.export_prefix = data.get("export_prefix", "")
        settings.prefix_before_name = data.get("prefix_before_name", True)
        settings.last_video_folder = data.get("last_video_folder")
        settings.export_format = data.get("export_format", "PNG")
        settings.jpeg_quality = data.get("jpeg_quality", 95)
        return settings


def load_settings() -> Settings:
    path = settings_file()
    if not path.exists():
        logger.info("No settings file yet, using defaults")
        return Settings()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Settings loaded")
        return Settings.from_dict(data)
    except (OSError, json.JSONDecodeError) as error:
        logger.error(f"Failed to load settings, using defaults: {error!r}")
        return Settings()


def save_settings(settings: Settings) -> None:
    path = settings_file()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Settings saved")
    except OSError as error:
        logger.error(f"Failed to save settings: {error!r}")
