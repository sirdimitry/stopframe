"""Opt-in release smoke test, using only generated media in a temporary folder."""
import json
import os
import subprocess
import tempfile
import sys
import time
from pathlib import Path


def run():
    # No access to the user's saved settings, source list, cache or logs.
    import stopframe.logging_setup as logs
    logs._configured = True
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    import cv2
    import numpy as np
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    from stopframe import __version__
    from stopframe.config import Settings
    from stopframe.core.face_check import worker_command
    from stopframe.core.exporter import export_frame
    from stopframe.core.video_probe import probe_video
    from stopframe.core.thumbnails import generate_filmstrip_thumbnails
    from stopframe.core.models import FrameCandidate, FrameOrigin, LogoPlacement
    from stopframe.resources import resource_path
    from stopframe.ui.widgets.about_dialog import AboutDialog
    from stopframe.ui.widgets.filmstrip_widget import FilmstripWidget
    from stopframe.ui.workers.auto_pick_worker import AutoPickWorker
    from stopframe.core import face_check
    from stopframe.core.performance import configure_threads
    configure_threads()

    assert __version__ != '0.0.0'
    app = QApplication.instance() or QApplication([])
    app.setStyle('Fusion')
    app.setStyleSheet(resource_path('stopframe', 'ui', 'theme', 'dark_orange.qss').read_text())
    assert resource_path('assets', 'branding', 'app-icon.png').is_file()
    dialog = AboutDialog()
    assert __version__ in dialog.version_label.text()
    dialog.show()
    app.processEvents()
    if os.environ.get('STOPFRAME_QA_DIR'):
        dest = Path(os.environ['STOPFRAME_QA_DIR'])
        dest.mkdir(parents=True, exist_ok=True)
        dialog.grab().save(str(dest / 'about.png'))
    dialog.close()

    with tempfile.TemporaryDirectory(prefix='stopframe-self-test-') as folder:
        root = Path(folder)
        path = root / 'sample.avi'
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
        assert writer.isOpened()
        for i in range(10):
            writer.write(np.full((48, 64, 3), i * 20, dtype=np.uint8))
        writer.release()
        video = probe_video(str(path))
        assert video and video.width == 64
        thumbs = generate_filmstrip_thumbnails(str(path), 5)
        assert len(thumbs) == 5
        strip = FilmstripWidget()
        strip.set_thumbnails(thumbs)
        assert not strip.grab().isNull()
        settings = Settings()
        slot = '4:3-landscape-left'
        logo = root / 'overlay.png'
        Image.new('RGBA', (64, 48), (255, 255, 255, 128)).save(logo)
        settings.logo_slots[slot].path = str(logo)
        candidate = FrameCandidate(str(path), 9, .9, FrameOrigin.MANUAL, LogoPlacement(slot, 0, 0, 1))
        exported = export_frame(candidate, settings, root)
        assert exported and exported.is_file()
        with Image.open(exported) as image:
            assert image.size == (64, 48)
            assert abs(image.getpixel((32, 24))[0] - 218) <= 3
        candidate.rotation_quarter_turns = 1
        candidate.logo_placement.slot_key = '4:3-portrait-left'
        settings.logo_slots['4:3-portrait-left'].path = str(logo)
        rotated = export_frame(candidate, settings, root)
        assert rotated and rotated.is_file()
        with Image.open(rotated) as image:
            assert image.size == (48, 64)
        blank = root / 'blank.npy'
        np.save(blank, np.zeros((240, 320, 3), dtype=np.uint8))
        result = subprocess.run(worker_command(),
            input=json.dumps({'frame_path': str(blank)}) + '\n' + json.dumps({'cmd': 'quit'}) + '\n',
            capture_output=True, text=True, timeout=40,
            env={**os.environ, 'MPLCONFIGDIR': str(root), 'XDG_CACHE_HOME': str(root)})
        assert result.returncode == 0, result.stderr[-2000:]
        response = json.loads(result.stdout.strip())
        assert response == {'face_found': False}, response
        worker = AutoPickWorker([video], settings, 2)
        native_path = face_check.native_worker_path()
        if native_path:
            geometry = subprocess.run([str(native_path), '--self-test'], capture_output=True, text=True,
                                      check=True, timeout=10)
            assert json.loads(geometry.stdout) == {'geometry': 'ok'}
        picks, progress, finished = [], [], []
        worker.candidate_ready.connect(picks.append)
        worker.progress.connect(lambda done, total: progress.append((done, total)))
        worker.finished_all.connect(lambda: finished.append(True))
        try:
            worker.start()
            assert worker.wait(45000), 'Automatic Pick did not finish within 45 seconds'
            app.processEvents()
            assert progress == [(1, 1)] and finished == [True]
            assert 0 < len(picks) <= 2
            assert worker.face_checks_available, 'Face checks unavailable in Automatic Pick'
            if native_path:
                assert face_check.backend_description().startswith('Apple Vision'), 'Native backend failed'
            assert 'mediapipe' not in sys.modules, 'MediaPipe imported in GUI process'
        finally:
            face_check.shutdown()

        # Exercise folder replacement with real decoders and render queues,
        # without loading or saving the user's preferences.
        from stopframe.core.capture_store import CaptureStore
        from stopframe.ui.tabs.settings_tab import SettingsTab
        from stopframe.ui.tabs.timeline_tab import TimelineTab
        from stopframe.ui.tabs.screenshots_tab import ScreenshotsTab
        session_settings = Settings(export_prefix='previous', export_format='JPEG',
                                    export_include_logo=False, frames_per_video=1)
        expected_settings = session_settings.to_dict()
        sources = []
        store = CaptureStore()
        setup = SettingsTab(session_settings, sources, store)
        timeline = TimelineTab(sources, session_settings, store)
        review = ScreenshotsTab(store, session_settings)
        setup.videos_changed.connect(timeline.refresh)
        setup.workspace_reset.connect(timeline.reset)
        setup.logos_changed.connect(review.refresh_logo_library)

        def wait_previews():
            deadline = time.monotonic() + 30
            while timeline._thumbnail_workers or review._render_workers:
                assert time.monotonic() < deadline, 'Previews did not finish'
                for preview_worker in timeline._thumbnail_workers + review._render_workers:
                    preview_worker.wait(20)
                app.processEvents()

        try:
            setup._add_video_paths([str(path)])
            store.add(candidate)
            setup._reset_workspace()
            app.processEvents()
            assert session_settings.to_dict() == expected_settings
            assert not sources and not store.frames and not review.cards and not timeline.rows
            assert timeline.frame_source is None and not timeline.capture_button.isEnabled()
            assert setup.prefix_edit.text() == 'previous' and not review.logo_toggle.isChecked()
            # A second session must still be able to decode and render.
            setup._add_video_paths([str(path)])
            timeline._on_capture_clicked()
            wait_previews()
            assert len(sources) == len(store.frames) == len(review.cards) == 1
            setup._reset_workspace()
            photos = root / 'photos'
            photos.mkdir()
            wide = photos / 'wide.jpg'
            other = photos / 'other.png'
            Image.new('RGB', (160, 90), 'black').save(wide)
            Image.new('RGB', (100, 150), 'black').save(other)
            setup._add_video_paths([str(wide), str(other)])
            assert len(store.frames) == len(review.cards) == 2
            assert not timeline.rows and not setup.auto_pick_button.isEnabled()
            assert [c.origin for c in store.frames] == [FrameOrigin.PHOTO] * 2
            assert [c.logo_placement.slot_key for c in store.frames] == [
                '16:9-landscape-left', '4:3-portrait-left']
            photo_settings = Settings(export_prefix='branded')
            for item in store.frames:
                photo_settings.logo_slots[item.logo_placement.slot_key].path = str(logo)
                result = export_frame(item, photo_settings, root / 'unused')
                assert result.parent == photos and result.name.startswith('branded-')
                with Image.open(result) as image:
                    expected_size = (160, 90) if item.video_path == str(wide) else (100, 150)
                    assert image.size == expected_size and image.getpixel((0, 0)) == (128, 128, 128)
            if sys.platform == 'darwin':
                heic = photos / 'native.heic'
                subprocess.run(['/usr/bin/sips', '-s', 'format', 'heic', str(wide), '--out', str(heic)],
                               check=True, capture_output=True, timeout=30)
                setup._add_video_paths([str(heic)])
                assert len(store.frames) == 3 and sources[-1].is_photo
                result = export_frame(store.frames[-1], photo_settings, root / 'unused')
                assert result and result.is_file()
            wait_previews()
            assert all(not card.image_label.pixmap().isNull() for card in review.cards.values())
        finally:
            setup.shutdown()
            timeline.shutdown()
            review.shutdown()
            setup.close()
            timeline.close()
            review.close()
    print(json.dumps({'version': __version__, 'resources': 'ok', 'about': 'ok',
                      'video_decode': 'ok', 'export': 'ok', 'face_worker': 'ok', 'auto_pick': 'ok',
                      'face_backend': face_check.backend_description(), 'rotation': 'ok',
                      'folder_reset': 'ok', 'photos': 'ok'}))

    # Optional real-media QA in the frozen app. This never loads saved settings
    # or exports images; it checks completion and progress of the actual worker.
    if os.environ.get('STOPFRAME_QA_VIDEO_FOLDER'):
        from stopframe.core.video_probe import find_videos_in_folder
        from stopframe.ui.tabs.settings_tab import SettingsTab
        from stopframe.core.capture_store import CaptureStore
        import logging
        errors = []
        class ErrorCollector(logging.Handler):
            def emit(self, record):
                if record.levelno >= logging.ERROR:
                    errors.append(record.getMessage())
        collector = ErrorCollector()
        logging.getLogger('stopframe').addHandler(collector)
        videos = [probe_video(path) for path in find_videos_in_folder(os.environ['STOPFRAME_QA_VIDEO_FOLDER'])]
        assert videos and all(videos), 'Unreadable videos in QA folder'
        tab = SettingsTab(Settings(frames_per_video=3), videos, CaptureStore())
        tab._start_auto_pick(videos)
        worker = tab._auto_pick_worker
        progress, detail, finished = [], [], []
        worker.progress.connect(lambda done, total: progress.append((done, total)))
        worker.video_progress.connect(lambda done, fraction: detail.append((done, fraction)))
        worker.finished_all.connect(lambda: finished.append(True))
        started = last_report = time.monotonic()
        try:
            while worker.isRunning():
                app.processEvents()
                if time.monotonic() - last_report >= 10:
                    print(json.dumps({'qa_progress': tab.auto_pick_status_label.text(),
                                      'percent': round(100 * tab.auto_pick_progress.value() /
                                                       tab.auto_pick_progress.maximum(), 1)}), flush=True)
                    last_report = time.monotonic()
                if time.monotonic() - started > 1800:
                    worker.request_cancel()
                    raise AssertionError('QA batch exceeded 30 minutes')
                worker.wait(20)
            app.processEvents()
            assert not errors, errors
            assert finished == [True] and progress[-1] == (len(videos), len(videos)), progress
            assert tab.auto_pick_progress.value() == tab.auto_pick_progress.maximum()
            assert any(0 < fraction < 1 for _, fraction in detail), 'Missing per-video progress'
            assert worker.face_checks_available, 'Face checks disabled during QA batch'
            print(json.dumps({'qa_videos': len(videos), 'qa_percent': 100,
                              'qa_seconds': round(time.monotonic() - started, 2),
                              'qa_errors': errors, 'version': __version__}), flush=True)
        finally:
            tab.shutdown()
            logging.getLogger('stopframe').removeHandler(collector)
