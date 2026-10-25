"""Large automatic selection counts and confirmation before any state changes."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QMessageBox
import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.models import AspectRatio, VideoItem
from stopframe.ui.tabs.settings_tab import SettingsTab


class PickCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_counts_survive_ui_and_settings_round_trip(self):
        for count in (6, 99, 100, 1000):
            with self.subTest(count=count), patch('stopframe.ui.tabs.settings_tab.save_settings'):
                settings = Settings.from_dict(Settings(frames_per_video=count).to_dict())
                tab = SettingsTab(settings, [], CaptureStore())
                self.assertEqual(tab.frames_per_video_spin.value(), count)
                tab.frames_per_video_spin.setValue(count + 1)
                self.assertEqual(Settings.from_dict(settings.to_dict()).frames_per_video, count + 1)
                tab.close()

    def test_threshold_and_yes_no_actions(self):
        for count, confirmed in ((99, False), (100, False), (100, True)):
            with self.subTest(count=count, confirmed=confirmed):
                video = VideoItem('test.mp4', 160, 90, 200, AspectRatio.RATIO_16_9, 30)
                tab = SettingsTab(Settings(frames_per_video=count), [video], CaptureStore())
                with patch.object(tab, '_confirm_long_search', return_value=confirmed) as confirm, \
                     patch('stopframe.ui.tabs.settings_tab.AutoPickWorker') as worker:
                    tab._on_auto_pick_clicked()
                    self.assertEqual(confirm.call_count, int(count > 99))
                    if count > 99 and not confirmed:
                        worker.assert_not_called()
                        self.assertIsNone(tab._auto_pick_worker)
                        self.assertFalse(tab._auto_picked_paths)
                        self.assertTrue(tab.auto_pick_button.isEnabled())
                        self.assertTrue(tab.frames_per_video_spin.isEnabled())
                    else:
                        worker.assert_called_once_with([video], tab.settings, count, tab)
                        worker.return_value.start.assert_called_once()
                        self.assertFalse(tab.frames_per_video_spin.isEnabled())
                tab._auto_pick_worker = None
                tab.close()

    def test_dialog_labels_default_and_escape(self):
        with patch('stopframe.ui.tabs.settings_tab.QMessageBox') as factory:
            factory.Icon = QMessageBox.Icon
            factory.StandardButton = QMessageBox.StandardButton
            factory.return_value.exec.return_value = QMessageBox.StandardButton.No
            self.assertFalse(SettingsTab._confirm_long_search(Mock()))
            dialog = factory.return_value
            self.assertIn('Поиск может занять много времени', dialog.setText.call_args.args[0])
            self.assertEqual([c.args[0] for c in dialog.button.return_value.setText.call_args_list], ['Да', 'Нет'])
            dialog.setDefaultButton.assert_called_once_with(QMessageBox.StandardButton.No)
            dialog.setEscapeButton.assert_called_once_with(QMessageBox.StandardButton.No)
            dialog.exec.return_value = QMessageBox.StandardButton.Yes
            self.assertTrue(SettingsTab._confirm_long_search(Mock()))
