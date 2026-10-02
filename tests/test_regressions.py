import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import gc
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent

# Tests must not touch the user's application settings or log files.
import stopframe.logging_setup as logging_setup
logging_setup._configured = True

from stopframe.config import Settings
from stopframe.core import auto_pick
from stopframe.core.compositor import compose_logo
from stopframe.core.exporter import export_frame
from stopframe.core.face_check import FaceQuality
from stopframe.core.frame_reader import FrameSource
from stopframe.core.models import AspectRatio, FrameCandidate, FrameOrigin, LogoPlacement, VideoItem
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
from stopframe.ui.tabs.timeline_tab import TimelineTab
from stopframe.ui.tabs.settings_tab import SettingsTab
from stopframe.core.capture_store import CaptureStore
from stopframe.ui.widgets.filmstrip_widget import FilmstripWidget, STRIP_HEIGHT
from stopframe.ui.workers.card_render_worker import CardRenderWorker
from stopframe.ui.workers.export_worker import ExportWorker


def candidate():
    return FrameCandidate('mock.avi', 0, 0, FrameOrigin.MANUAL,
                          LogoPlacement('16:9-landscape-left', 0, 0, 1))


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_transparent_logo_and_offsets(self):
        overlay = Image.new('RGBA', (2, 2), (255, 255, 255, 128))
        with patch('stopframe.core.compositor._fitted_overlay', return_value=overlay):
            result = compose_logo(Image.new('RGB', (2, 2), 'black'), 'mock',
                                  LogoPlacement('mock', 1, 0, 1))
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))
        self.assertEqual(result.getpixel((1, 0)), (128, 128, 128))

    def test_two_frame_setting_survives_wheel_and_settings_round_trip(self):
        settings = Settings(frames_per_video=2)
        with patch('stopframe.ui.tabs.settings_tab.save_settings'):
            tab = SettingsTab(settings, [], CaptureStore())
            spin = tab.frames_per_video_spin
            self.assertEqual(spin.value(), 2)
            event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(), QPoint(0, 120),
                                Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(spin, event)
            self.assertEqual(spin.value(), 2)
            spin.setValue(1)
            self.assertEqual(Settings.from_dict(settings.to_dict()).frames_per_video, 1)
            tab.deleteLater()

    def test_auto_pick_releases_pixels_and_keeps_bucket_winners(self):
        refs = []
        source = Mock()
        def read(timestamp):
            gc.collect()
            self.assertFalse(any(ref() is not None for ref in refs))
            frame = np.full((2, 2, 3), timestamp + 1, dtype=np.uint8)
            refs.append(weakref.ref(frame))
            return frame
        source.read_at.side_effect = read
        video = VideoItem('mock', 1920, 1080, 12, AspectRatio.RATIO_16_9, 30)
        with patch.object(auto_pick, 'FrameSource', return_value=source), \
             patch.object(auto_pick, 'are_similar', return_value=False), \
             patch.object(auto_pick, 'laplacian_variance', new=lambda f: float(f[0, 0, 0]) + 100), \
             patch.object(auto_pick, 'check_face_quality', new=lambda f: FaceQuality(False)):
            results = auto_pick.pick_frames_for_video(video, Settings(), 4)
        self.assertEqual([c.timestamp_seconds for c in results], [2, 5, 8, 11])
        source.close.assert_called_once()

    def test_auto_pick_rejects_bad_faces_and_preserves_sharpness_floor(self):
        source = Mock()
        source.read_at.side_effect = lambda t: np.full((1, 1, 3), int(t), np.uint8)
        scores = [100, 80, 20, 60, 90, 70]
        video = VideoItem('mock', 10, 10, 6, AspectRatio.OTHER, 30)
        with patch.object(auto_pick, 'FrameSource', return_value=source), \
             patch.object(auto_pick, 'are_similar', return_value=False), \
             patch.object(auto_pick, 'laplacian_variance', new=lambda f: scores[int(f[0, 0, 0])]), \
             patch.object(auto_pick, 'check_face_quality', new=lambda f: FaceQuality(True, eyes_open=int(f[0, 0, 0]) != 0)):
            results = auto_pick.pick_frames_for_video(video, Settings(), 3)
        self.assertEqual([c.timestamp_seconds for c in results], [1, 3, 4])

    def test_auto_pick_cancel_releases_source(self):
        source = Mock()
        with patch.object(auto_pick, 'FrameSource', return_value=source):
            result = auto_pick.pick_frames_for_video(
                VideoItem('mock', 10, 10, 6, AspectRatio.OTHER), Settings(), is_cancelled=lambda: True)
        self.assertEqual(result, [])
        source.read_at.assert_not_called()
        source.close.assert_called_once()

    def test_unreadable_manual_capture_is_not_added(self):
        tab = Mock(active_index=0)
        tab.frame_source.read_at.return_value = None
        tab._timestamp_at_playhead.return_value = 0
        with patch('stopframe.ui.tabs.timeline_tab.QMessageBox.warning') as warning:
            TimelineTab._on_capture_clicked(tab)
        tab.capture_store.add.assert_not_called()
        warning.assert_called_once()

    def test_auto_pick_closes_source_on_error(self):
        source = Mock()
        source.read_at.side_effect = RuntimeError('decode')
        with patch.object(auto_pick, 'FrameSource', return_value=source):
            with self.assertRaises(RuntimeError):
                auto_pick.pick_frames_for_video(VideoItem('mock', 10, 10, 3, AspectRatio.OTHER), Settings())
        source.close.assert_called_once()

    def test_export_directory_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'logo').write_text('existing file')
            with patch('stopframe.core.exporter.FrameSource') as source:
                source.return_value.read_at.return_value = np.zeros((2, 2, 3), dtype=np.uint8)
                self.assertIsNone(export_frame(candidate(), Settings(), Path(tmp)))
            self.assertEqual((Path(tmp) / 'logo').read_text(), 'existing file')

    def test_export_continues_and_finishes_after_failure(self):
        worker = ExportWorker([candidate(), candidate()], Settings(), Path('/mock'))
        finished, progress = [], []
        worker.finished_all.connect(finished.append)
        worker.progress.connect(lambda done, total: progress.append((done, total)))
        with patch('stopframe.ui.workers.export_worker.export_frame',
                   side_effect=[PermissionError(), Path('/mock/logo/success.png')]):
            worker.run()
        self.assertEqual(worker.failed_count, 1)
        self.assertEqual(finished, [['/mock/logo']])
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_stale_card_result_ignored_and_worker_has_snapshot(self):
        original = candidate()
        worker = CardRenderWorker(original, None, 1)
        original.logo_placement.offset_x = 20
        original.hdr_fix = True
        self.assertEqual(worker.candidate.logo_placement.offset_x, 0)
        self.assertFalse(worker.candidate.hdr_fix)
        card = Mock()
        tab = Mock(_render_revisions={original.id: 2}, cards={original.id: card})
        ScreenshotsTab._on_card_rendered(tab, original.id, 1, Image.new('RGB', (2, 2)))
        card.set_pixmap.assert_not_called()
        ScreenshotsTab._on_card_rendered(tab, original.id, 2, Image.new('RGB', (2, 2)))
        card.set_pixmap.assert_called_once()

    def test_end_of_video_is_readable_and_step_back_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'sample.avi')
            writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
            self.assertTrue(writer.isOpened())
            for i in range(10):
                writer.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
            writer.release()
            video = VideoItem(path, 64, 48, 1, AspectRatio.RATIO_4_3, 10)
            strip = FilmstripWidget()
            strip.set_position(1)
            tab = Mock(active_index=0, rows=[Mock(filmstrip=strip)])
            tab._timestamp_at_playhead = lambda v: TimelineTab._timestamp_at_playhead(tab, v)
            tab._active_video.return_value = video
            timestamp = tab._timestamp_at_playhead(video)
            self.assertAlmostEqual(timestamp, .9)
            source = FrameSource(path)
            try:
                frame = source.read_at(timestamp)
                self.assertIsNotNone(frame)
                self.assertAlmostEqual(float(frame.mean()), 180, delta=3)
            finally:
                source.close()
            TimelineTab._step_frame(tab, -1)
            self.assertAlmostEqual(strip.position_fraction, .8)

    def test_filmstrip_uses_natural_aspect_and_whole_video(self):
        strip = FilmstripWidget()
        strip.resize(720, STRIP_HEIGHT + 6)
        strip.set_thumbnails([np.full((90, 160, 3), i * 4, np.uint8) for i in range(60)])
        tiles = strip._visible_tiles()
        self.assertLess(len(tiles), 10)
        self.assertEqual(tiles[0][0], 0)
        self.assertEqual(tiles[-1][0], 59)
        for _, rect in tiles:
            self.assertAlmostEqual(rect.width() / rect.height(), 16 / 9)
        strip.resize(360, STRIP_HEIGHT + 6)
        self.assertLess(len(strip._visible_tiles()), len(tiles))
        self.assertFalse(strip.grab().isNull())


if __name__ == '__main__':
    unittest.main()
