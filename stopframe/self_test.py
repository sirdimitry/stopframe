"""Opt-in release smoke test, using only generated media in a temporary folder."""
import json
import os
import subprocess
import tempfile
import sys
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
    print(json.dumps({'version': __version__, 'resources': 'ok', 'about': 'ok',
                      'video_decode': 'ok', 'export': 'ok', 'face_worker': 'ok', 'auto_pick': 'ok',
                      'face_backend': face_check.backend_description(), 'rotation': 'ok'}))
