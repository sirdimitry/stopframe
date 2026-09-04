"""Generates a video's filmstrip thumbnails off the UI thread, so adding a
folder full of long clips doesn't freeze the window. Checks the on-disk
cache first — reopening the same video is then near-instant."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from stopframe.core.thumbnail_cache import load_cached_thumbnails, save_thumbnails_to_cache
from stopframe.core.thumbnails import generate_filmstrip_thumbnails


class ThumbnailWorker(QThread):
    finished_with_thumbnails = Signal(str, list)  # video_path, list[np.ndarray]

    def __init__(self, video_path: str, count: int, parent=None) -> None:
        super().__init__(parent)
        self.video_path = video_path
        self.count = count

    def run(self) -> None:
        cached = load_cached_thumbnails(self.video_path, self.count)
        if cached is not None:
            self.finished_with_thumbnails.emit(self.video_path, cached)
            return

        thumbnails = generate_filmstrip_thumbnails(self.video_path, self.count)
        if thumbnails:
            save_thumbnails_to_cache(self.video_path, self.count, thumbnails)
        self.finished_with_thumbnails.emit(self.video_path, thumbnails)
