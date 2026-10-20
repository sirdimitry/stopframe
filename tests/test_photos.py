"""Photo import, EXIF-aware logos, shared preview and safe source-folder export."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from PySide6.QtWidgets import QApplication

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core.exporter import export_frame
from stopframe.core.frame_reader import FrameSource
from stopframe.core.models import AspectRatio, FrameOrigin, VideoItem
from stopframe.core.video_probe import find_media_in_folder, probe_photo
from stopframe.ui.main_window import MainWindow
from stopframe.ui.workers.card_render_worker import CardRenderWorker


class PhotoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='stopframe-photo-test-')
        self.root = Path(self.temp.name)
        self.patches = [
            patch('stopframe.ui.main_window.load_settings', return_value=Settings()),
            patch('stopframe.ui.main_window.QSettings'),
            patch('stopframe.ui.tabs.settings_tab.save_settings'),
            patch('stopframe.ui.tabs.screenshots_tab.save_settings'),
            patch('stopframe.ui.tabs.timeline_tab.ThumbnailWorker'),
            patch('stopframe.ui.tabs.timeline_tab.FrameSource'),
        ]
        mocks = [p.start() for p in self.patches]
        mocks[1].return_value.value.return_value = None
        mocks[-1].return_value.read_at.return_value = None
        self.window = MainWindow()
        self.window.screenshots_tab._render_card = Mock()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def photo(self, name='photo.png', size=(160, 90), exif=None):
        path = self.root / name
        kwargs = {'exif': exif} if exif else {}
        Image.new('RGB', size, (20, 40, 60)).save(path, **kwargs)
        return str(path)

    def test_photos_choose_templates_without_capture_or_analysis(self):
        sizes = [(160, 90), (90, 160), (150, 100), (100, 150), (100, 100)]
        keys = ['16:9-landscape-left', '16:9-portrait-left', '4:3-landscape-left',
                '4:3-portrait-left', '4:3-landscape-left']
        paths = [self.photo(f'{i}.png', size) for i, size in enumerate(sizes)]
        with patch('stopframe.ui.tabs.settings_tab.probe_video') as probe, \
             patch('stopframe.ui.tabs.settings_tab.AutoPickWorker') as worker:
            self.window.settings_tab._add_video_paths(paths + paths[:1])
            self.window.settings_tab._on_auto_pick_clicked()
            probe.assert_not_called()
            worker.assert_not_called()
        self.assertEqual(len(self.window.videos), len(sizes))
        frames = self.window.capture_store.frames
        self.assertEqual([f.logo_placement.slot_key for f in frames], keys)
        self.assertTrue(all(f.origin == FrameOrigin.PHOTO for f in frames))
        self.assertEqual(len(self.window.screenshots_tab.cards), len(sizes))
        self.assertTrue(all(c.badge.text() == 'ФОТО' for c in self.window.screenshots_tab.cards.values()))
        self.assertFalse(self.window.timeline_tab.rows)
        self.assertFalse(self.window.settings_tab.auto_pick_button.isEnabled())

    def test_mixed_import_only_analyzes_videos(self):
        photo = self.photo()
        video = VideoItem('/sample.mp4', 160, 90, 1, AspectRatio.RATIO_16_9, 10)
        with patch('stopframe.ui.tabs.settings_tab.probe_video', return_value=video):
            self.window.settings_tab._add_video_paths([photo, video.path])
        self.assertEqual([r.video.path for r in self.window.timeline_tab.rows], [video.path])
        self.assertTrue(self.window.settings_tab.auto_pick_button.isEnabled())
        with patch.object(self.window.settings_tab, '_start_auto_pick') as pick:
            self.window.settings_tab._on_auto_pick_clicked()
            pick.assert_called_once_with([video])

    def test_exif_orientation_agrees_in_probe_reader_preview_and_export(self):
        exif = Image.Exif()
        exif[274] = 6
        path = self.photo('rotated.jpg', exif=exif)
        item = probe_photo(path)
        self.assertEqual((item.width, item.height), (90, 160))
        self.window.settings_tab._add_video_paths([path])
        candidate = self.window.capture_store.frames[0]
        self.assertEqual(candidate.logo_placement.slot_key, '16:9-portrait-left')
        with patch('stopframe.core.frame_reader.cv2.VideoCapture') as capture:
            source = FrameSource(path)
            self.assertEqual(source.read_at(0).shape[:2], (160, 90))
            source.close()
            capture.assert_not_called()
        renders = []
        worker = CardRenderWorker(candidate, None)
        worker.finished_render.connect(lambda _id, _rev, image: renders.append(image))
        worker.run()
        self.assertEqual(renders[0].size, (90, 160))
        exported = export_frame(candidate, self.window.settings, self.root / 'ignored')
        with Image.open(exported) as image:
            self.assertEqual(image.size, (90, 160))

    def test_photo_export_applies_matched_logo_and_preserves_original(self):
        path = self.photo('original.png', (150, 100))
        original = Path(path).read_bytes()
        overlay = self.root / 'overlay.png'
        Image.new('RGBA', (12, 8), (255, 0, 0, 255)).save(overlay)
        settings = self.window.settings
        settings.export_prefix = 'brand'
        settings.logo_slots['4:3-landscape-left'].path = str(overlay)
        self.window.settings_tab._add_video_paths([path])
        candidate = self.window.capture_store.frames[0]
        exported = export_frame(candidate, settings, self.root / 'ignored')
        self.assertEqual(exported, self.root / 'brand-original.png')
        self.assertEqual(Path(path).read_bytes(), original)
        self.assertFalse((self.root / 'logo').exists())
        with Image.open(exported) as image:
            self.assertEqual(image.size, (150, 100))
            self.assertEqual(image.getpixel((75, 50)), (255, 0, 0))

    def test_photo_export_suffix_jpeg_and_collision_never_overwrite(self):
        path = self.photo('source.png')
        self.window.settings_tab._add_video_paths([path])
        settings = self.window.settings
        settings.export_prefix = 'brand'
        settings.prefix_before_name = False
        settings.export_format = 'JPEG'
        existing = self.root / 'source-brand.jpg'
        existing.write_bytes(b'keep')
        candidate = self.window.capture_store.frames[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: export_frame(candidate, settings, self.root), range(2)))
        self.assertEqual(len(set(results)), 2)
        self.assertEqual(existing.read_bytes(), b'keep')
        for result in results:
            self.assertTrue(result.name.startswith('source-brand_'))
            with Image.open(result) as image:
                self.assertEqual(image.format, 'JPEG')

    def test_photo_export_uses_logo_when_prefix_is_empty(self):
        path = self.photo('source.png')
        self.window.settings_tab._add_video_paths([path])
        result = export_frame(self.window.capture_store.frames[0], self.window.settings, self.root)
        self.assertEqual(result.name, 'logo-source.png')

    def test_photos_only_export_does_not_ask_for_destination(self):
        path = self.photo()
        self.window.settings_tab._add_video_paths([path])
        with patch('stopframe.ui.main_window.QFileDialog.getExistingDirectory') as choose, \
             patch('stopframe.ui.main_window.ExportWorker') as worker, \
             patch('stopframe.ui.main_window.QProgressDialog'):
            self.window._on_export_clicked()
            choose.assert_not_called()
            worker.return_value.start.assert_called_once()
        self.window._export_worker = None

    def test_folder_loads_photos_and_preserves_logo_settings(self):
        path = self.photo()
        settings = self.window.settings
        settings.export_prefix = 'keep'
        settings.logo_slots['16:9-landscape-left'].offset_x = 7
        with patch('stopframe.ui.tabs.settings_tab.QFileDialog.getExistingDirectory', return_value=str(self.root)):
            self.window.settings_tab._on_add_folder()
        self.assertEqual(len(self.window.capture_store.frames), 1)
        self.assertEqual(self.window.capture_store.frames[0].video_path, path)
        self.assertEqual(self.window.capture_store.frames[0].logo_placement.offset_x, 7)
        self.assertEqual(settings.export_prefix, 'keep')
        self.assertEqual(find_media_in_folder(str(self.root)), [path])

    def test_unreadable_photo_is_skipped_without_video_decode(self):
        path = self.root / 'broken.jpg'
        path.write_text('not an image')
        with patch('stopframe.ui.tabs.settings_tab.probe_video') as probe:
            self.window.settings_tab._add_video_paths([str(path)])
            probe.assert_not_called()
        self.assertFalse(self.window.videos)
        self.assertFalse(self.window.capture_store.frames)
