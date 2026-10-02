import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.exporter import export_frame
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement
from stopframe.core.rotation import rotate_frame
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
from stopframe.ui.workers.card_render_worker import CardRenderWorker
from stopframe.ui.widgets.frame_detail_dialog import FrameDetailDialog


def candidate():
    return FrameCandidate('mock', 0, 0, FrameOrigin.MANUAL,
                          LogoPlacement('16:9-landscape-right', 12, 6, 1.2))


class RotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_clockwise_pixels_and_four_turn_cycle_are_lossless(self):
        frame = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)
        np.testing.assert_array_equal(rotate_frame(frame, 1), [[4, 1], [5, 2], [6, 3]])
        self.assertTrue(rotate_frame(frame, 1).flags.c_contiguous)
        rotated = frame
        for _ in range(4):
            rotated = rotate_frame(rotated, 1)
        np.testing.assert_array_equal(rotated, frame)
        self.assertIs(rotate_frame(frame, 4), frame)

    def test_button_rotates_only_selected_frames_and_keeps_logo_adjustments(self):
        store = CaptureStore()
        first, second, untouched = candidate(), candidate(), candidate()
        store.frames.extend([first, second, untouched])
        with patch.object(ScreenshotsTab, '_render_card') as render:
            tab = ScreenshotsTab(store, Settings())
            self.assertFalse(tab.rotate_button.isEnabled())
            tab.selected_ids = {first.id, second.id}
            tab._update_hdr_button_state()
            self.assertTrue(tab.rotate_button.isEnabled())
            render.reset_mock()
            for turn in range(1, 5):
                tab.rotate_button.click()
                self.assertEqual(first.rotation_quarter_turns, turn % 4)
                self.assertEqual(second.rotation_quarter_turns, turn % 4)
                self.assertEqual(untouched.rotation_quarter_turns, 0)
                expected = 'portrait' if turn % 2 else 'landscape'
                self.assertEqual(first.logo_placement.slot_key, f'16:9-{expected}-right')
                self.assertEqual((first.logo_placement.offset_x, first.logo_placement.offset_y, first.logo_placement.scale), (12, 6, 1.2))
            self.assertEqual(render.call_count, 8)
            tab.shutdown()

    def test_card_detail_and_export_agree_on_clockwise_rotation(self):
        frame = np.zeros((2, 3, 3), np.uint8)
        frame[:, :, 2] = [[10, 20, 30], [40, 50, 60]]
        original = candidate()
        original.rotation_quarter_turns = 1
        settings = Settings(export_include_logo=False)
        source = Mock()
        source.read_at.return_value = frame
        images = []
        worker = CardRenderWorker(original, None)
        worker.finished_render.connect(lambda cid, revision, image: images.append(image))
        with patch('stopframe.ui.workers.card_render_worker.FrameSource', return_value=source):
            worker.run()
        expected = np.array([[40, 10], [50, 20], [60, 30]])
        self.assertEqual(images[0].size, (2, 3))
        np.testing.assert_array_equal(np.asarray(images[0])[:, :, 0], expected)
        with patch('stopframe.ui.widgets.frame_detail_dialog.FrameSource', return_value=source):
            dialog = FrameDetailDialog(original, settings)
            self.assertEqual(dialog.pixmap_item.pixmap().size().width(), 2)
            self.assertEqual(dialog.pixmap_item.pixmap().size().height(), 3)
            dialog.close()
        with tempfile.TemporaryDirectory() as folder, \
             patch('stopframe.core.exporter.FrameSource', return_value=source):
            path = export_frame(original, settings, Path(folder))
            with Image.open(path) as exported:
                self.assertEqual(exported.size, (2, 3))
                np.testing.assert_array_equal(np.asarray(exported)[:, :, 0], expected)
        self.assertEqual(original.rotation_quarter_turns, 1)


if __name__ == '__main__':
    unittest.main()
