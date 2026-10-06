import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
import numpy as np
from PySide6.QtWidgets import QApplication
from stopframe.config import Settings
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement
from stopframe.ui.widgets.frame_detail_dialog import FrameDetailDialog


def frame(path, x=0):
    return FrameCandidate(path, 0, 1, FrameOrigin.MANUAL,
                          LogoPlacement('16:9-landscape-left', x, 0, 1))


class DetailControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.first, self.second = frame('first', 12), frame('second', 35)
        source = Mock()
        source.read_at.return_value = np.zeros((48, 64, 3), np.uint8)
        self.decoder = patch('stopframe.ui.widgets.frame_detail_dialog.FrameSource', return_value=source)
        self.factory = self.decoder.start()
        self.dialog = FrameDetailDialog(self.first, Settings(), candidates=[self.first, self.second])

    def tearDown(self):
        self.dialog.close()
        self.decoder.stop()

    def test_navigation_preserves_edits_and_restores_each_frames_controls(self):
        d = self.dialog
        changed = []
        d.candidate_changed.connect(changed.append)
        self.assertFalse(d.previous_button.isEnabled())
        d.hdr_button.click()
        d.offset_x_slider.setValue(19)
        self.assertTrue(self.first.hdr_fix)
        d.next_button.click()
        self.assertIs(d.candidate, self.second)
        self.assertFalse(d.next_button.isEnabled())
        self.assertFalse(d.hdr_button.isChecked())
        self.assertEqual(d.offset_x_slider.value(), 35)
        self.assertEqual(self.second.logo_placement.offset_x, 35)
        d.previous_button.click()
        self.assertTrue(d.hdr_button.isChecked())
        self.assertEqual(d.offset_x_slider.value(), 19)
        self.assertEqual(changed, [self.first, self.first])

    def test_four_rotations_restore_pixels_and_side_matches_orientation(self):
        d = self.dialog
        d.rotate_button.click()
        self.assertEqual(self.first.rotation_quarter_turns, 1)
        self.assertEqual(self.first.logo_placement.slot_key, '16:9-portrait-left')
        self.assertEqual(d.pixmap_item.pixmap().width(), 48)
        d.right_button.click()
        self.assertEqual(self.first.logo_placement.slot_key, '16:9-portrait-right')
        self.assertTrue(d.right_button.isChecked())
        for _ in range(3):
            d.rotate_button.click()
        self.assertEqual(self.first.rotation_quarter_turns, 0)
        self.assertEqual(self.first.logo_placement.slot_key, '16:9-landscape-right')
        self.assertEqual(d.pixmap_item.pixmap().width(), 64)
        self.assertEqual(self.factory.call_count, 1)

    def test_single_frame_and_unreadable_next_frame_keep_navigation_safe(self):
        d = self.dialog
        d._navigate(-1)
        self.assertIs(d.candidate, self.first)
        self.factory.return_value.read_at.return_value = None
        d.next_button.click()
        self.assertTrue(d.error_text_item.isVisible())
        self.assertTrue(d.pixmap_item.pixmap().isNull())
        d._navigate(1)
        self.assertIs(d.candidate, self.second)
        single = FrameDetailDialog(self.first, Settings())
        self.assertFalse(single.previous_button.isEnabled())
        self.assertFalse(single.next_button.isEnabled())
        single.close()
