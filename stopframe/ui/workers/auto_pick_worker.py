"""Runs automatic frame selection across every source video off the UI
thread, reporting progress per video and streaming results as they're
produced instead of waiting for the whole batch."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from stopframe.config import Settings
from stopframe.core.auto_pick import pick_frames_for_video
from stopframe.core.models import VideoItem
from stopframe.logging_setup import get_logger

logger = get_logger("ui.auto_pick_worker")


class AutoPickWorker(QThread):
    progress = Signal(int, int)  # videos done, total
    candidate_ready = Signal(object)  # FrameCandidate
    finished_all = Signal()

    def __init__(self, videos: list[VideoItem], settings: Settings, target_count: int, parent=None) -> None:
        super().__init__(parent)
        self.videos = list(videos)
        self.settings = settings
        self.target_count = target_count

    def run(self) -> None:
        total = len(self.videos)
        for index, video in enumerate(self.videos):
            try:
                for candidate in pick_frames_for_video(video, self.settings, self.target_count):
                    self.candidate_ready.emit(candidate)
            except Exception as error:  # keep the batch going even if one video fails
                logger.error(f"Auto pick failed for {video.file_name}: {error!r}")
            self.progress.emit(index + 1, total)
        self.finished_all.emit()
