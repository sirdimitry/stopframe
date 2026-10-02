import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication,QPushButton,QGroupBox
from stopframe.config import Settings
from stopframe.core.capture_store import CaptureStore
from stopframe.core.models import FrameCandidate,FrameOrigin,LogoPlacement
from stopframe.ui.tabs.settings_tab import SettingsTab
from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
import stopframe.logging_setup as logs
logs._configured=True


class LogoLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_logo_chooser_lives_in_settings_dialog_and_emits_library_updates(self):
        settings=Settings()
        setup=SettingsTab(settings,[],CaptureStore())
        chooser=next(b for b in setup.logo_settings_dialog.findChildren(QPushButton) if b.text()=='Choose Logos Folder…')
        self.assertNotEqual(chooser.objectName(),'primaryButton')
        self.assertFalse(setup.logo_settings_dialog.isVisible())
        self.assertEqual(setup.logo_settings_dialog.windowTitle(),'Logo Library')
        updated=[];setup.logos_changed.connect(lambda:updated.append(True))
        with patch('stopframe.ui.tabs.settings_tab.match_logos_in_folder',return_value={}):
            setup._rescan_logos_folder('/mock',persist=False)
        self.assertEqual(updated,[True])
        setup.deleteLater()

    def test_badge_checks_real_files_and_required_templates(self):
        settings=Settings();store=CaptureStore();review=ScreenshotsTab(store,settings)
        self.assertEqual(review.logo_status_button.property('status'),'missing')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'logo.png';path.write_bytes(b'fixture')
            key='16:9-landscape-left';settings.logo_slots[key].path=str(path)
            review.refresh_logo_status()
            self.assertEqual(review.logo_status_button.property('status'),'partial')
            frame=FrameCandidate('mock',0,0,FrameOrigin.AUTO,LogoPlacement(key,0,0,1))
            store.frames=[frame];review.refresh_logo_status()
            self.assertEqual(review.logo_status_button.property('status'),'ready')
            self.assertFalse(review.logo_status_button.icon().isNull())
            frame.logo_placement.slot_key='16:9-portrait-left';review.refresh_logo_status()
            self.assertEqual(review.logo_status_button.property('status'),'partial')
            self.assertEqual(review.logo_status_button.text(),'Logo templates missing')
            path.unlink();review.refresh_logo_status()
            self.assertEqual(review.logo_status_button.property('status'),'missing')
        opened=[];review.logo_settings_requested.connect(lambda:opened.append(True))
        review.logo_status_button.click();self.assertEqual(opened,[True])
        review.shutdown();review.deleteLater()


if __name__=='__main__':unittest.main()
