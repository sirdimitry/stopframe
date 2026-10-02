"""Exports every included capture off the UI thread, reporting progress
and collecting the set of destination folders touched so the caller can
open them in Finder once the batch finishes."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from stopframe.logging_setup import get_logger

logger = get_logger("ui.export_worker")

from PySide6.QtCore import QThread, Signal

from stopframe.config import Settings
from stopframe.core.exporter import export_frame
from stopframe.core.models import FrameCandidate
from stopframe.core.performance import EXPORT_CONCURRENCY


class ExportWorker(QThread):
    progress = Signal(int, int)  # done, total
    finished_all = Signal(list)  # list[str] of unique destination folders

    def __init__(self, candidates: list[FrameCandidate], settings: Settings, dest_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.candidates = deepcopy(candidates)
        self.settings = deepcopy(settings)
        self.failed_count = 0
        self.dest_root = dest_root
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        folders: set[str] = set()
        total = len(self.candidates)
        try:
            with ThreadPoolExecutor(max_workers=EXPORT_CONCURRENCY, thread_name_prefix="stopframe-export") as pool:
                candidates = iter(self.candidates)
                pending = set()
                done_count = 0
                while True:
                    while not self._cancel_requested and len(pending) < EXPORT_CONCURRENCY:
                        candidate = next(candidates, None)
                        if candidate is None:
                            break
                        pending.add(pool.submit(export_frame, candidate, self.settings, self.dest_root))
                    if not pending:
                        break
                    completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in completed:
                        try:
                            path = future.result()
                            if path is not None:
                                folders.add(str(path.parent))
                            else:
                                self.failed_count += 1
                        except Exception as error:
                            self.failed_count += 1
                            logger.error("Export failed: %s", type(error).__name__)
                        done_count += 1
                        self.progress.emit(done_count, total)
        finally:
            self.finished_all.emit(sorted(folders))
