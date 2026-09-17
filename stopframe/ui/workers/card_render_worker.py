"""Renders one screenshot card's thumbnail (frame + optional HDR fix +
logo) off the UI thread — reading and decoding a frame is too slow to do
inline every time a card is added or its logo/placement changes."""

from __future__ import annotations

from copy import deepcopy

from PIL import Image
from PySide6.QtCore import QThread, Signal

from stopframe.core.compositor import compose_logo, frame_to_image
from stopframe.core.frame_reader import FrameSource
from stopframe.core.hdr_fix import apply_hdr_fix
from stopframe.core.models import FrameCandidate


class CardRenderWorker(QThread):
    finished_render = Signal(str, int, object)  # candidate.id, revision, PIL.Image.Image | None

    def __init__(self, candidate: FrameCandidate, logo_path: str | None, revision: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.candidate = deepcopy(candidate)
        self.revision = revision
        self.logo_path = logo_path

    def run(self) -> None:
        source = FrameSource(self.candidate.video_path)
        try:
            frame = source.read_at(self.candidate.timestamp_seconds)
        finally:
            source.close()
        if frame is None:
            self.finished_render.emit(self.candidate.id, self.revision, None)
            return

        if self.candidate.hdr_fix:
            frame = apply_hdr_fix(frame)

        image: Image.Image = frame_to_image(frame)
        composed = compose_logo(image, self.logo_path, self.candidate.logo_placement)
        self.finished_render.emit(self.candidate.id, self.revision, composed)
