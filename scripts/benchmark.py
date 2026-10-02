#!/usr/bin/env python3
"""Compare analysis pipelines on local videos; write no exports or settings.

Usage: .venv/bin/python scripts/benchmark.py /path/to/videos --count 8
Reference: full-size frames, FFmpeg decoder, MediaPipe, original OpenCV threads.
Optimized: bounded frames, AVFoundation, Apple Vision, bounded OpenCV threads.
Run each pipeline in a fresh process so model startup is included independently.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def measure(paths, reference):
    import stopframe.logging_setup as logs
    logs._configured = True
    import cv2
    from stopframe.config import Settings
    from stopframe.core import auto_pick, face_check
    from stopframe.core.frame_reader import FrameSource
    from stopframe.core.performance import configure_threads
    from stopframe.core.video_probe import probe_video

    videos = [probe_video(str(path)) for path in paths]
    videos = [video for video in videos if video]
    if not reference:
        configure_threads()
    timing, counts = [], []
    from contextlib import ExitStack
    with ExitStack() as stack:
        if reference:
            stack.enter_context(patch.object(auto_pick, 'bounded_frame', side_effect=lambda frame, edge: frame))
            stack.enter_context(patch.object(auto_pick, 'FrameSource', side_effect=lambda path, **kw: FrameSource(path, decoder_threads=0)))
            stack.enter_context(patch.object(face_check, 'native_worker_path', return_value=None))
        try:
            for video in videos:
                start = time.perf_counter()
                counts.append(len(auto_pick.pick_frames_for_video(video, Settings(), 2)))
                timing.append(time.perf_counter() - start)
            backend = face_check.backend_description()
        finally:
            face_check.shutdown()
    return {'pipeline': 'reference' if reference else 'optimized', 'backend': backend,
            'videos': len(videos), 'source_seconds': sum(v.duration_seconds for v in videos),
            'analysis_seconds': sum(timing), 'first_video_seconds': timing[0] if timing else None,
            'picks': counts, 'opencv_threads': cv2.getNumThreads()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--pipeline', choices=['reference', 'optimized'])
    args = parser.parse_args()
    paths = sorted(path for path in args.folder.iterdir() if path.suffix.lower() in {'.mp4', '.mov', '.mkv', '.avi'})[:args.count]
    if not paths:
        parser.error('No videos found')
    if args.pipeline:
        print(json.dumps(measure(paths, args.pipeline == 'reference')))
        return
    results = []
    for pipeline in ['reference', 'optimized']:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(args.folder),
                                 '--count', str(args.count), '--pipeline', pipeline],
                                check=True, capture_output=True, text=True)
        results.append(json.loads(result.stdout))
    print(json.dumps({'results': results,
                      'speedup': results[0]['analysis_seconds'] / results[1]['analysis_seconds']}, indent=2))


if __name__ == '__main__':
    main()
