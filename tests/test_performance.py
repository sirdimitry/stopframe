import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import numpy as np
import cv2
from PIL import Image
from PySide6.QtWidgets import QApplication

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core import compositor, face_check
from stopframe.core.capture_store import CaptureStore
from stopframe.core.exporter import export_frame
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement
from stopframe.core.performance import bounded_frame, configure_threads
from stopframe.core.frame_reader import FrameSource
from stopframe.ui.workers.export_worker import ExportWorker
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
from stopframe.ui.workers.card_render_worker import CardRenderWorker


def candidate():
    return FrameCandidate('mock', 0, 0, FrameOrigin.AUTO,
                          LogoPlacement('16:9-landscape-left', 12, 6, 1))


class PerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_analysis_size_preserves_aspect_and_never_upscales(self):
        frame = np.zeros((2160, 3840, 3), np.uint8)
        self.assertEqual(bounded_frame(frame, 960).shape, (540, 960, 3))
        small = np.zeros((48, 64, 3), np.uint8)
        self.assertIs(bounded_frame(small, 960), small)

    def test_threads_are_actually_bounded_with_gcd(self):
        configure_threads()
        self.assertEqual(cv2.getNumThreads(), 1)

    def test_native_decoder_falls_back_on_unreadable_frame(self):
        native, legacy = Mock(), Mock()
        native.read.return_value = (False, None)
        expected = np.zeros((10, 10, 3), np.uint8)
        legacy.read.return_value = (True, expected)
        with patch('stopframe.core.frame_reader.sys.platform', 'darwin'), \
             patch('stopframe.core.frame_reader.cv2.VideoCapture', side_effect=[native, legacy]):
            source = FrameSource('mock', native_decode=True)
            self.assertIs(source.read_at(2), expected)
            native.release.assert_called_once()
            legacy.set.assert_called_with(cv2.CAP_PROP_POS_MSEC, 2000)
            source.close()

    def test_cancelled_export_does_not_schedule_remaining_batch(self):
        worker = ExportWorker([candidate() for _ in range(20)], Settings(), Path('/mock'))
        calls, finished = [], []
        worker.finished_all.connect(finished.append)
        def export(*args):
            calls.append(args)
            worker.request_cancel()
            return Path('/mock/logo/output.png')
        with patch('stopframe.ui.workers.export_worker.export_frame', side_effect=export):
            worker.run()
        self.assertLessEqual(len(calls), 2)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(finished, [['/mock/logo']])

    def test_card_renders_proxy_with_scaled_offsets_and_preserves_candidate(self):
        original = candidate()
        worker = CardRenderWorker(original, None)
        source = Mock()
        source.read_at.return_value = np.zeros((1080, 1920, 3), np.uint8)
        rendered = []
        worker.finished_render.connect(lambda cid, revision, image: rendered.append(image))
        with patch('stopframe.ui.workers.card_render_worker.FrameSource', return_value=source), \
             patch('stopframe.ui.workers.card_render_worker.compose_logo', side_effect=lambda image, path, placement: image) as compose:
            worker.run()
        self.assertEqual(rendered[0].size, (640, 360))
        placement = compose.call_args.args[2]
        self.assertEqual((placement.offset_x, placement.offset_y), (4, 2))
        self.assertEqual((original.logo_placement.offset_x, original.logo_placement.offset_y), (12, 6))

    def test_preview_queue_caps_concurrency_and_coalesces_updates(self):
        tab = ScreenshotsTab(CaptureStore(), Settings())
        frames = [candidate() for _ in range(4)]
        for frame in frames:
            tab.cards[frame.id] = Mock()
        with patch('stopframe.ui.tabs.screenshots_tab.CardRenderWorker') as factory:
            for frame in frames:
                tab._render_card(frame)
            self.assertEqual(factory.call_count, 2)
            self.assertEqual(len(tab._pending_renders), 2)
            frames[-1].logo_placement.offset_x = 99
            tab._render_card(frames[-1])
            self.assertEqual(len(tab._pending_renders), 2)
            self.assertEqual(tab._pending_renders[frames[-1].id][0].logo_placement.offset_x, 99)
            tab._render_workers.pop()
            tab._start_pending_renders()
            self.assertEqual(factory.call_count, 3)
        tab._render_workers.clear()
        tab.shutdown()
        self.assertEqual(tab._pending_renders, {})

    def test_native_error_falls_back_once(self):
        with patch.object(face_check, '_worker_backend', 'appleVision'), \
             patch.object(face_check, '_native_failed', False), \
             patch.object(face_check, '_availability_checked', True), \
             patch.object(face_check, '_available', True), \
             patch.object(face_check, 'shutdown') as shutdown:
            self.assertTrue(face_check._fallback_to_mediapipe())
            self.assertTrue(face_check._native_failed)
            self.assertFalse(face_check._availability_checked)
            self.assertIsNone(face_check.native_worker_path())
            shutdown.assert_called_once()

    def test_overlay_cache_invalidates_and_obeys_memory_limit(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(compositor, '_overlays', compositor.OrderedDict()), \
             patch.object(compositor, '_overlay_bytes', 0), \
             patch.object(compositor, '_OVERLAY_CACHE_BYTES', 500):
            path = Path(folder) / 'logo.png'
            Image.new('RGBA', (10, 10), 'red').save(path)
            first = compositor._fitted_overlay(str(path), (10, 10))
            self.assertIs(compositor._fitted_overlay(str(path), (10, 10)), first)
            Image.new('RGBA', (10, 10), 'blue').save(path)
            changed = compositor._fitted_overlay(str(path), (10, 10))
            self.assertEqual(changed.getpixel((0, 0)), (0, 0, 255, 255))
            self.assertLessEqual(compositor._overlay_bytes, 500)

    def test_parallel_export_collision_preserves_existing_file_and_full_resolution(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder)
            (dest / 'logo').mkdir()
            original = dest / 'logo' / 'same.png'
            original.write_bytes(b'keep me')
            source = Mock()
            source.read_at.return_value = np.zeros((1080, 1920, 3), np.uint8)
            with patch('stopframe.core.exporter.FrameSource', return_value=source), \
                 patch('stopframe.core.exporter.build_export_filename', return_value='same.png'):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    paths = list(pool.map(lambda _: export_frame(candidate(), Settings(), dest), range(2)))
            self.assertEqual(len(set(paths)), 2)
            self.assertEqual(original.read_bytes(), b'keep me')
            for path in paths:
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1920, 1080))


if __name__ == '__main__':
    unittest.main()
