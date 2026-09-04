"""Generates a video's filmstrip thumbnails off the UI thread, so adding a
folder full of long clips doesn't freeze the window."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from stopframe.core.thumbnails import generate_filmstrip_thumbnails


class ThumbnailWorker(QThread):
    finished_with_thumbnails = Signal(str, list)  # video_path, list[np.ndarray]

    def __init__(self, video_path: str, count: int, parent=None) -> None:
        super().__init__(parent)
        self.video_path = video_path
        self.count = count

    def run(self) -> None:
        thumbnails = generate_filmstrip_thumbnails(self.video_path, self.count)
        self.finished_with_thumbnails.emit(self.video_path, thumbnails)
