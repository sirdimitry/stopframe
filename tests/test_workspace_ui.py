"""Behavior checks for empty, selected and busy workspace states."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from stopframe.config import Settings
from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement
from stopframe.ui.main_window import MainWindow


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with patch("stopframe.ui.main_window.load_settings", return_value=Settings()), \
             patch("stopframe.ui.main_window.QSettings") as preferences:
            preferences.return_value.value.return_value = None
            self.window = MainWindow()
        self.window.screenshots_tab._render_card = Mock()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window._export_worker = None
        self.window.close()

    def candidate(self):
        return FrameCandidate("/tmp/test-video.mp4", 0, 0, FrameOrigin.MANUAL,
                              LogoPlacement("16:9_landscape_left", 0, 0, 1))

    def test_capture_review_exclude_updates_export_and_selection(self):
        w = self.window
        w.tabs.setCurrentIndex(2)
        self.assertTrue(w.export_button.isVisible())
        self.assertFalse(w.export_button.isEnabled())
        self.assertTrue(w.screenshots_tab.empty_state.isVisible())
        self.assertFalse(w.timeline_tab.capture_button.isEnabled())
        self.assertFalse(w.settings_tab.auto_pick_button.isEnabled())
        candidate = self.candidate()
        w.capture_store.add(candidate)
        self.assertTrue(w.export_button.isEnabled())
        self.assertFalse(w.screenshots_tab.empty_state.isVisible())
        w.screenshots_tab.selected_ids = {candidate.id}
        w.screenshots_tab._refresh_selection_styles()
        self.assertTrue(all(b.isEnabled() for b in w.screenshots_tab.selection_buttons))
        w.screenshots_tab._on_exclude(candidate.id)
        self.assertFalse(w.export_button.isEnabled())
        self.assertTrue(w.screenshots_tab.empty_state.isVisible())
        self.assertFalse(any(b.isEnabled() for b in w.screenshots_tab.selection_buttons))

    def test_busy_export_remains_unavailable_across_navigation(self):
        w = self.window
        w.capture_store.add(self.candidate())
        w._export_worker = Mock()
        w.tabs.setCurrentIndex(2)
        self.assertFalse(w.export_button.isEnabled())
        self.assertIn("Экспортируем", w.export_button.text())
        w.tabs.setCurrentIndex(0)
        self.assertFalse(w.export_bar.isVisible())
        w.tabs.setCurrentIndex(2)
        self.assertTrue(w.export_button.isVisible())
        self.assertFalse(w.export_button.isEnabled())

    def test_card_can_be_selected_and_opened_with_keyboard(self):
        w = self.window
        candidate = self.candidate()
        w.capture_store.add(candidate)
        w.tabs.setCurrentIndex(2)
        card = w.screenshots_tab.cards[candidate.id]
        QTest.keyClick(card, Qt.Key.Key_Space)
        self.assertEqual(w.screenshots_tab.selected_ids, {candidate.id})
        with patch("stopframe.ui.tabs.screenshots_tab.FrameDetailDialog") as detail:
            QTest.keyClick(card, Qt.Key.Key_Return)
        detail.return_value.exec.assert_called_once()
