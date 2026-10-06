import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from stopframe.ui.tabs.timeline_tab import TimelineTab, THUMBNAIL_CONCURRENCY
from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore


class ThumbnailQueueTests(unittest.TestCase):
    def test_large_folder_limits_decoders_and_discards_removed_sources(self):
        app = QApplication.instance() or QApplication([])
        tab = TimelineTab([], Settings(), CaptureStore())
        tab.rows = [Mock(video=Mock(path=str(i))) for i in range(150)]
        tab._pending_thumbnails = [str(i) for i in range(150)]
        with patch('stopframe.ui.tabs.timeline_tab.ThumbnailWorker') as factory:
            factory.side_effect = lambda *args: Mock()
            tab._start_pending_thumbnails()
            self.assertEqual(factory.call_count, THUMBNAIL_CONCURRENCY)
            self.assertEqual(len(tab._pending_thumbnails), 148)
            completed = tab._thumbnail_workers[0]
            tab.rows = [r for r in tab.rows if r.video.path != '2']
            with patch.object(tab, 'sender', return_value=completed):
                tab._on_thumbnail_worker_finished()
            self.assertEqual(len(tab._thumbnail_workers), THUMBNAIL_CONCURRENCY)
            self.assertEqual(factory.call_args.args[0], '3')
            completed.deleteLater.assert_called_once()
            tab.shutdown()
            self.assertFalse(tab._pending_thumbnails)
            calls = factory.call_count
            tab._start_pending_thumbnails()
            self.assertEqual(factory.call_count, calls)
        tab.rows = []
        tab.close()
