import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.models import AspectRatio, VideoItem
from stopframe.ui.tabs.settings_tab import SettingsTab
from stopframe.ui.workers.auto_pick_worker import AutoPickWorker


class AutoPickProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_worker_reports_fractional_progress_before_video_finishes(self):
        videos = [VideoItem(str(i), 128, 128, 30, AspectRatio.OTHER, 30) for i in range(2)]
        worker = AutoPickWorker(videos, Settings(), 3)
        details, completed, finished = [], [], []
        worker.video_progress.connect(lambda done, fraction: details.append((done, fraction)))
        worker.progress.connect(lambda done, total: completed.append((done, total)))
        worker.finished_all.connect(lambda: finished.append(True))
        def pick(video, settings, count, *, is_cancelled, on_progress):
            on_progress('sharpness', 30, 30)
            on_progress('faces', 30, 30)
            return []
        with patch('stopframe.ui.workers.auto_pick_worker.is_available', return_value=True), \
             patch('stopframe.ui.workers.auto_pick_worker.pick_frames_for_video', side_effect=pick):
            worker.run()
        self.assertEqual(details, [(0, .5), (0, 1), (1, .5), (1, 1)])
        self.assertEqual(completed, [(1, 2), (2, 2)])
        self.assertEqual(finished, [True])

    def test_partial_progress_does_not_mark_cancelled_video_as_complete(self):
        videos = [VideoItem(str(i), 128, 128, 30, AspectRatio.OTHER, 30) for i in range(3)]
        tab = SettingsTab(Settings(), videos, CaptureStore())
        with patch('stopframe.ui.tabs.settings_tab.AutoPickWorker') as factory:
            factory.return_value.face_checks_available = True
            tab._start_auto_pick(videos)
            tab._on_auto_pick_progress(1, 3)
            tab._on_auto_pick_video_progress(1, .5)
            self.assertEqual(tab.auto_pick_progress.value(), 1500)
            self.assertEqual(tab._last_auto_pick_done, 1)
            tab._stop_auto_pick()
            tab._on_auto_pick_video_progress(1, .9)
            self.assertEqual(tab.auto_pick_progress.value(), 1500)
            tab._on_auto_pick_finished()
        self.assertEqual(tab._auto_picked_paths, {'0'})
        self.assertTrue(tab.auto_pick_button.isEnabled())
        tab.shutdown()
