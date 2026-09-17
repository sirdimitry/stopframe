import unittest
import io
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

import stopframe.logging_setup as logs
logs._configured = True
from stopframe.config import Settings
from stopframe.core import auto_pick
from stopframe.core.face_check import FaceQuality
from stopframe.core.face_check_worker import _check_one, _LEFT_EYE, _RIGHT_EYE, _MOUTH
from stopframe.core.frame_similarity import fingerprint, are_similar
from stopframe.core.models import VideoItem, AspectRatio


def scene(seed):
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 255, (8, 8, 3), dtype=np.uint8)
    return cv2.resize(small, (128, 128), interpolation=cv2.INTER_NEAREST)


def run_pick(frames, face=None, scores=None, read=None):
    source = Mock()
    source.read_at.side_effect = read or (lambda t: frames[min(int(t), len(frames) - 1)].copy())
    video = VideoItem('mock', 128, 128, len(frames), AspectRatio.OTHER, 30)
    with patch.object(auto_pick, 'FrameSource', return_value=source), \
         patch.object(auto_pick, 'check_face_quality', new=face or (lambda f: FaceQuality(False))), \
         patch.object(auto_pick, 'laplacian_variance', new=scores or (lambda f: 100)):
        return auto_pick.pick_frames_for_video(video, Settings(), 4)


def face_landmarks(width, height, left=0.25, right=0.25, mouth=0.05):
    points = [SimpleNamespace(x=0.5, y=0.5) for _ in range(468)]
    for indices, ratio, center in [(_LEFT_EYE, left, (40, 30)),
                                   (_RIGHT_EYE, right, (80, 30)),
                                   (_MOUTH, mouth, (60, 65))]:
        top, bottom, outer, inner = indices
        x, y = center
        for index, px, py in [(outer, x - 10, y), (inner, x + 10, y),
                              (top, x, y - ratio * 10), (bottom, x, y + ratio * 10)]:
            points[index] = SimpleNamespace(x=px / width, y=py / height)
    return SimpleNamespace(landmark=points)


class QualityTests(unittest.TestCase):
    def test_face_worker_error_disables_checks_instead_of_silent_success(self):
        from stopframe.core import face_check
        worker = Mock()
        worker.stdout = io.StringIO('{"error": "initialization failed"}\n')
        worker.stdin = io.StringIO()
        with patch.object(face_check, 'is_available', return_value=True), \
             patch.object(face_check, '_ensure_worker', return_value=worker), \
             patch.object(face_check.select, 'select', return_value=([worker.stdout], [], [])), \
             patch.object(face_check, '_disable') as disable:
            result = face_check.check_face_quality(np.zeros((2, 2, 3), np.uint8))
        self.assertFalse(result.face_found)
        disable.assert_called_once()

    def test_static_scene_yields_one(self):
        result = run_pick([scene(1)] * 12)
        self.assertEqual(len(result), 1)

    def test_small_noise_and_exposure_change_are_duplicates(self):
        original = scene(1)
        rng = np.random.default_rng(2)
        changed = np.clip(original.astype(float) + 5 + rng.normal(0, 2, original.shape), 0, 255).astype(np.uint8)
        self.assertTrue(are_similar(fingerprint(original), fingerprint(changed)))

    def test_same_palette_different_composition_is_kept(self):
        original = scene(3)
        moved = np.roll(original, 48, axis=1)
        self.assertFalse(are_similar(fingerprint(original), fingerprint(moved)))
        self.assertEqual(len(run_pick([original] * 4 + [moved] * 4)), 2)

    def test_four_scenes_preserve_time_coverage(self):
        result = run_pick([scene(i // 3) for i in range(12)])
        self.assertEqual(len(result), 4)
        self.assertEqual([int(c.timestamp_seconds // 3) for c in result], [0, 1, 2, 3])

    def test_alternative_scene_fills_duplicate_bucket_winner(self):
        a, b = scene(1), scene(2)
        result = run_pick([a, b, a, a, a, a, a, a])
        self.assertEqual(len(result), 2)
        self.assertIn(1, [c.timestamp_seconds for c in result])

    def test_closed_eyes_never_filled_to_reach_target(self):
        result = run_pick([scene(i) for i in range(8)], face=lambda f: FaceQuality(True, eyes_open=False))
        self.assertEqual(result, [])

    def test_open_mouth_never_filled_to_reach_target(self):
        result = run_pick([scene(i) for i in range(8)], face=lambda f: FaceQuality(True, mouth_closed=False))
        self.assertEqual(result, [])

    def test_neighbor_recovers_blink(self):
        def read(t):
            f = scene(1)
            f[0, 0, 0] = 1 if abs(t - round(t)) > .01 else 0
            return f
        result = run_pick([scene(1)] * 3, read=read,
                          face=lambda f: FaceQuality(True, eyes_open=bool(f[0, 0, 0])))
        self.assertEqual(len(result), 1)
        self.assertGreater(abs(result[0].timestamp_seconds - round(result[0].timestamp_seconds)), .01)

    def test_undetected_neighbor_does_not_replace_bad_face(self):
        def read(t):
            f = scene(1)
            f[0, 0, 0] = 1 if abs(t - round(t)) > .01 else 0
            return f
        result = run_pick([scene(1)] * 3, read=read,
                          face=lambda f: FaceQuality(not bool(f[0, 0, 0]), eyes_open=False))
        self.assertEqual(result, [])

    def test_face_geometry_is_independent_of_video_aspect(self):
        for width, height in [(1920, 1080), (1080, 1920), (640, 480)]:
            mesh = Mock()
            mesh.process.return_value.multi_face_landmarks = [face_landmarks(width, height)]
            with patch('stopframe.core.face_check_worker.np.load', return_value=np.zeros((height, width, 3), np.uint8)):
                result = _check_one(mesh, 'unused')
            self.assertTrue(result['eyes_open'])
            self.assertTrue(result['mouth_closed'])

    def test_one_closed_eye_fails_even_if_other_is_wide_open(self):
        mesh = Mock()
        mesh.process.return_value.multi_face_landmarks = [face_landmarks(640, 480, left=.05, right=.5)]
        with patch('stopframe.core.face_check_worker.np.load', return_value=np.zeros((480, 640, 3), np.uint8)):
            self.assertFalse(_check_one(mesh, 'unused')['eyes_open'])

    def test_second_face_open_mouth_rejects_group_frame(self):
        mesh = Mock()
        mesh.process.return_value.multi_face_landmarks = [face_landmarks(640, 480), face_landmarks(640, 480, mouth=.4)]
        with patch('stopframe.core.face_check_worker.np.load', return_value=np.zeros((480, 640, 3), np.uint8)):
            result = _check_one(mesh, 'unused')
        self.assertTrue(result['eyes_open'])
        self.assertFalse(result['mouth_closed'])


if __name__ == '__main__':
    unittest.main()
