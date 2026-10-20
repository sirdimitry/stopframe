"""A folder starts a fresh session, including queued work from the old one."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core.models import AspectRatio, FrameCandidate, FrameOrigin, LogoPlacement, VideoItem
from stopframe.ui.main_window import MainWindow
from stopframe.ui.workers.auto_pick_worker import AutoPickWorker


class FolderResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.patches = [
            patch("stopframe.ui.main_window.load_settings", return_value=Settings()),
            patch("stopframe.ui.main_window.QSettings"),
            patch("stopframe.ui.tabs.settings_tab.save_settings"),
            patch("stopframe.ui.tabs.screenshots_tab.save_settings"),
            patch("stopframe.ui.tabs.timeline_tab.ThumbnailWorker"),
            patch("stopframe.ui.tabs.timeline_tab.FrameSource"),
        ]
        mocks = [p.start() for p in self.patches]
        mocks[1].return_value.value.return_value = None
        mocks[-1].return_value.read_at.return_value = None
        self.saved = mocks[2]
        self.window = MainWindow()
        self.window.screenshots_tab._render_card = Mock()

    def tearDown(self):
        self.window.settings_tab._auto_pick_worker = None
        self.window.close()
        self.app.processEvents()
        for p in reversed(self.patches):
            p.stop()

    def video(self, path):
        return VideoItem(path, 64, 48, 1, AspectRatio.RATIO_4_3, 10)

    def frame(self, path):
        return FrameCandidate(path, 0, 0, FrameOrigin.AUTO,
                              LogoPlacement("4:3-landscape-left", 12, 5, 1.3),
                              hdr_fix=True, rotation_quarter_turns=1)

    def open_folder(self, folder, paths):
        with patch("stopframe.ui.tabs.settings_tab.QFileDialog.getExistingDirectory", return_value=folder), \
             patch("stopframe.ui.tabs.settings_tab.find_media_in_folder", return_value=paths), \
             patch("stopframe.ui.tabs.settings_tab.probe_video", side_effect=self.video):
            self.window.settings_tab._on_add_folder()

    def test_folder_clears_old_work_but_preserves_settings_and_logos(self):
        w = self.window
        tab = w.settings_tab
        old = self.video("/old/clip.mp4")
        w.videos.append(old)
        w.timeline_tab.refresh()
        source = w.timeline_tab.frame_source
        frame = self.frame(old.path)
        w.capture_store.add(frame)
        review = w.screenshots_tab
        review.selected_ids = {frame.id}
        review.anchor_id = frame.id
        review._pending_renders[frame.id] = (frame, None, 1)
        review._render_revisions[frame.id] = 1
        tab.prefix_edit.setText("old")
        tab.prefix_after_radio.setChecked(True)
        tab.format_combo.setCurrentText("JPEG")
        tab.jpeg_quality_spin.setValue(20)
        tab.frames_per_video_spin.setValue(1)
        review.logo_toggle.setChecked(False)
        w.settings.logos_folder = "/old/logos"
        w.settings.logo_slots["4:3-landscape-left"].path = "/old/logo.png"
        w.settings.logo_slots["4:3-landscape-left"].offset_x = 17
        expected = w.settings.to_dict()
        expected['last_video_folder'] = '/new'
        tab._auto_picked_paths.add(old.path)
        worker = Mock()
        tab._auto_pick_worker = worker
        tab.auto_pick_progress.setValue(80)
        tab.auto_pick_status_label.setText("Old analysis")

        self.open_folder("/new", ["/new/clip.mp4"])

        worker.request_cancel.assert_called_once()
        worker.wait.assert_called_once()
        source.close.assert_called_once()
        self.assertEqual(w.settings.to_dict(), expected)
        self.assertTrue(all(t.settings is w.settings for t in (tab, w.timeline_tab, review)))
        self.assertEqual([v.path for v in w.videos], ["/new/clip.mp4"])
        self.assertEqual([r.video.path for r in w.timeline_tab.rows], ["/new/clip.mp4"])
        self.assertEqual(w.capture_store.frames, [])
        self.assertEqual(review.cards, {})
        self.assertEqual(review._group_video_order, [])
        self.assertEqual(review.selected_ids, set())
        self.assertIsNone(review.anchor_id)
        self.assertFalse(review._pending_renders)
        self.assertFalse(review._render_revisions)
        self.assertFalse(w.export_button.isEnabled())
        self.assertFalse(any(b.isEnabled() for b in review.selection_buttons))
        self.assertFalse(review.logo_toggle.isChecked())
        self.assertEqual(tab.prefix_edit.text(), "old")
        self.assertTrue(tab.prefix_after_radio.isChecked())
        self.assertEqual(tab.format_combo.currentText(), "JPEG")
        self.assertEqual(tab.jpeg_quality_spin.value(), 20)
        self.assertTrue(tab.jpeg_quality_spin.isEnabled())
        self.assertEqual(tab.frames_per_video_spin.value(), 1)
        self.assertTrue(tab.frames_per_video_spin.isEnabled())
        self.assertEqual(tab.auto_pick_progress.value(), 0)
        self.assertEqual(tab.auto_pick_status_label.text(), "")
        self.assertFalse(tab._auto_picked_paths)
        self.saved.assert_called_with(w.settings)

    def test_queued_old_results_cannot_return_when_same_folder_reopens(self):
        w = self.window
        tab = w.settings_tab
        path = "/same/clip.mp4"
        w.videos.append(self.video(path))
        worker = AutoPickWorker(w.videos, w.settings, 1, tab)
        with patch("stopframe.ui.tabs.settings_tab.AutoPickWorker", return_value=worker), \
             patch("stopframe.ui.workers.auto_pick_worker.is_available", return_value=True), \
             patch("stopframe.ui.workers.auto_pick_worker.pick_frames_for_video", return_value=[self.frame(path)]):
            tab._start_auto_pick(w.videos)
            self.assertTrue(worker.wait(5000))
        # The worker finished, but its queued GUI signals have not run yet.
        self.open_folder("/same", [path])
        new_worker = Mock()
        tab._auto_pick_worker = new_worker
        self.app.processEvents()
        self.assertEqual(w.capture_store.frames, [])
        self.assertEqual(tab.auto_pick_status_label.text(), "")
        self.assertEqual(tab.auto_pick_progress.value(), 0)
        self.assertIs(tab._auto_pick_worker, new_worker)

    def test_cancelled_folder_dialog_preserves_session(self):
        w = self.window
        w.videos.append(self.video("/old/clip.mp4"))
        w.capture_store.add(self.frame(w.videos[0].path))
        w.settings.export_prefix = "keep"
        self.open_folder("", [])
        self.assertEqual(len(w.videos), 1)
        self.assertEqual(len(w.capture_store.frames), 1)
        self.assertEqual(w.settings.export_prefix, "keep")
        self.saved.assert_not_called()

    def test_empty_folder_also_clears_preview_and_captures(self):
        w = self.window
        w.videos.append(self.video("/old/clip.mp4"))
        w.timeline_tab.refresh()
        w.capture_store.add(self.frame(w.videos[0].path))
        self.open_folder("/empty", [])
        self.assertEqual(w.videos, [])
        self.assertEqual(w.capture_store.frames, [])
        self.assertEqual(w.timeline_tab.rows, [])
        self.assertIsNone(w.timeline_tab.frame_source)
        self.assertIsNone(w.timeline_tab.active_index)
        self.assertFalse(w.timeline_tab.capture_button.isEnabled())
        self.assertEqual(w.timeline_tab.preview_label.text(), "Выберите видео на ленте")
        self.assertFalse(w.settings_tab.auto_pick_button.isEnabled())

    def test_adding_single_video_preserves_existing_work(self):
        w = self.window
        w.videos.append(self.video("/old/clip.mp4"))
        w.capture_store.add(self.frame(w.videos[0].path))
        w.settings.export_prefix = "keep"
        with patch("stopframe.ui.tabs.settings_tab.QFileDialog.getOpenFileNames", return_value=(["/new/clip.mp4"], "")), \
             patch("stopframe.ui.tabs.settings_tab.probe_video", side_effect=self.video):
            w.settings_tab._on_add_file()
        self.assertEqual(len(w.videos), 2)
        self.assertEqual(len(w.capture_store.frames), 1)
        self.assertEqual(w.settings.export_prefix, "keep")
