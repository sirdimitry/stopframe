"""Runs automatic frame selection across every source video off the UI
thread, reporting progress per video and streaming results as they're
produced instead of waiting for the whole batch."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from stopframe.config import Settings
from stopframe.core.auto_pick import pick_frames_for_video
from stopframe.core.face_check import is_available, backend_description
from stopframe.core.models import VideoItem
from stopframe.logging_setup import get_logger

logger = get_logger("ui.auto_pick_worker")


class AutoPickWorker(QThread):
    progress = Signal(int, int)  # videos done, total
    candidate_ready = Signal(object)  # FrameCandidate
    finished_all = Signal()
    status = Signal(str)

    def __init__(self, videos: list[VideoItem], settings: Settings, target_count: int, parent=None) -> None:
        super().__init__(parent)
        self.videos = list(videos)
        self.settings = settings
        self.target_count = target_count
        self._cancel_requested = False
        self.face_checks_available = True

    def request_cancel(self) -> None:
        """Fire-and-forget: run() notices this within roughly one frame's
        worth of I/O (see pick_frames_for_video's is_cancelled polling),
        not just between whole videos — a video that's still being sampled
        can otherwise block for as long as that single video takes."""
        self._cancel_requested = True

    def _is_cancelled(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        total = len(self.videos)
        self.status.emit("Preparing face analysis…")
        if not self._cancel_requested:
            self.face_checks_available = is_available()
            self.status.emit("Analyzing videos…")
        for index, video in enumerate(self.videos):
            if self._cancel_requested:
                break
            try:
                for candidate in pick_frames_for_video(
                    video, self.settings, self.target_count, is_cancelled=self._is_cancelled
                ):
                    if self._cancel_requested:
                        break
                    self.candidate_ready.emit(candidate)
            except Exception as error:  # keep the batch going even if one video fails
                logger.error(f"Auto pick failed for {video.file_name}: {error!r}")
            if self._cancel_requested:
                break
            self.progress.emit(index + 1, total)
        self.face_checks_available = is_available()
        self.finished_all.emit()
