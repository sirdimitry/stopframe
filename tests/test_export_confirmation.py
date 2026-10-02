import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import stopframe.logging_setup as logs
logs._configured = True
from PySide6.QtWidgets import QMessageBox
from stopframe.ui.main_window import MainWindow


def window(logo_enabled=False, confirmed=False):
    return Mock(_export_worker=None,
                capture_store=Mock(frames=[Mock(included=True)]),
                settings=Mock(export_include_logo=logo_enabled, last_video_folder='/source'),
                _confirm_export_without_logo=Mock(return_value=confirmed))


class ExportConfirmationTests(unittest.TestCase):
    def test_cancel_without_logo_does_not_choose_folder_or_start_worker(self):
        current = window()
        with patch('stopframe.ui.main_window.QFileDialog.getExistingDirectory') as choose, \
             patch('stopframe.ui.main_window.ExportWorker') as worker:
            MainWindow._on_export_clicked(current)
        current._confirm_export_without_logo.assert_called_once()
        choose.assert_not_called()
        worker.assert_not_called()
        current.export_button.setEnabled.assert_not_called()

    def test_ok_without_logo_and_logo_enabled_both_proceed_to_export(self):
        for enabled in (False, True):
            with self.subTest(logo_enabled=enabled):
                current = window(logo_enabled=enabled, confirmed=True)
                with patch('stopframe.ui.main_window.QFileDialog.getExistingDirectory', return_value='/output'), \
                     patch('stopframe.ui.main_window.QProgressDialog'), \
                     patch('stopframe.ui.main_window.ExportWorker') as worker:
                    MainWindow._on_export_clicked(current)
                worker.assert_called_once_with(current.capture_store.frames, current.settings, Path('/output'))
                worker.return_value.start.assert_called_once()
                self.assertEqual(current._confirm_export_without_logo.call_count, 0 if enabled else 1)

    def test_empty_export_has_no_logo_confirmation(self):
        current = window()
        current.capture_store.frames = []
        with patch('stopframe.ui.main_window.QMessageBox.information'), \
             patch('stopframe.ui.main_window.QFileDialog.getExistingDirectory') as choose:
            MainWindow._on_export_clicked(current)
        current._confirm_export_without_logo.assert_not_called()
        choose.assert_not_called()

    def test_dialog_has_requested_labels_and_cancel_is_default(self):
        with patch('stopframe.ui.main_window.QMessageBox') as factory:
            # The patched constructor still uses actual Qt enums for behavior.
            factory.Icon = QMessageBox.Icon
            factory.StandardButton = QMessageBox.StandardButton
            factory.return_value.exec.return_value = QMessageBox.StandardButton.Cancel
            self.assertFalse(MainWindow._confirm_export_without_logo(Mock()))
            dialog = factory.return_value
            self.assertIn('Логотип выключен', dialog.setText.call_args.args[0])
            self.assertIn('Экспортировать без логотипа?', dialog.setText.call_args.args[0])
            dialog.setDefaultButton.assert_called_once_with(QMessageBox.StandardButton.Cancel)
            dialog.setEscapeButton.assert_called_once_with(QMessageBox.StandardButton.Cancel)
            self.assertEqual([c.args[0] for c in dialog.button.return_value.setText.call_args_list], ['ОК', 'Отменить'])


if __name__ == '__main__':
    unittest.main()
