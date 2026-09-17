import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import stopframe.logging_setup as logs
logs._configured = True
from stopframe import __version__
from stopframe.about import about_text
from stopframe.core.face_check import worker_command
from stopframe.resources import resource_path
from scripts.bump_version import bump


class PackagingTests(unittest.TestCase):
    def test_source_version_and_credit(self):
        expected = resource_path('VERSION').read_text().strip()
        self.assertEqual(__version__, expected)
        self.assertIn(expected, about_text())
        self.assertIn('навайбкодил- @sirdimitry', about_text())

    def test_bundle_face_worker_does_not_start_python_module(self):
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(worker_command(), [sys.executable, '--face-worker'])

    def test_source_face_worker_keeps_python_module(self):
        with patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(worker_command(), [sys.executable, '-m', 'stopframe.core.face_check_worker'])

    def test_release_version_rollover(self):
        self.assertEqual(bump(0, 0, 20), (0, 1, 0))
        self.assertEqual(bump(0, 10, 20), (1, 0, 0))

    def test_release_assets_present(self):
        for name in ['app-icon.png', 'banner.png', 'dmg-background.png']:
            self.assertTrue(resource_path('assets', 'branding', name).is_file())


if __name__ == '__main__':
    unittest.main()
