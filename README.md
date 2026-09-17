# StopFrame

A macOS desktop app for pulling clean, sharp still frames out of video and stamping a logo on them — fast, in bulk, with a manual fallback for the shots that need a human eye. Works with any source video; no assumptions about camera or subject.

## What it does

- **Auto pick** — scans each video for sharp frames, rejects detected closed eyes/open mouths, and checks nearby moments to recover blinks. Spatial fingerprints suppress near-duplicates while time buckets preserve coverage. The chosen 3–5 frames is a maximum: a static scene can yield just one frame, and a video without acceptable candidates can yield none. Face checks examine up to five detected faces and require optional MediaPipe; the UI reports when unavailable. Detection and similarity thresholds are heuristics, so manual review remains useful.
- **Auto logo placement** — splits each frame into left/right thirds, measures which side is visually "busier" (edge density, detected faces), and places the logo on the calmer side.
- **Manual timeline** — a scrubbable filmstrip per video with a live, logo-composited preview, frame-by-frame stepping, and a capture shortcut for the shots the heuristics miss.
- **Review grid** — every captured frame in one place, tagged auto/manual, with multi-select and one-click logo side/aspect reassignment before export.
- **Export** — writes finished frames back next to the source video, at full resolution, named with a configurable prefix.

## Privacy & security

StopFrame is fully local. It never makes a network call, never uploads a video, a frame, or a log line anywhere. All settings, thumbnails, and logs stay on disk under `~/Library/Application Support/StopFrame`. The log file is capped at 10 MB and trimmed to the last 100 lines; it records UI actions and processing results only — never file paths, images, or other user data.

## Status

Early scaffold — settings persistence, data models, versioning, and logging are in place; the UI and processing engine are next. See the version scheme below for how progress is tracked.

## Tech stack

- Python 3.11+
- PySide6 (Qt for Python) for the UI
- OpenCV for frame extraction, sharpness scoring, and edge-density analysis
- mediapipe (optional, degrades gracefully) for face landmark checks
- Pillow for logo compositing
- ffmpeg (via imageio-ffmpeg or the system binary) as a faster/more precise fallback for filmstrip thumbnails and seeking

## Versioning

Version is `MAJOR.MINOR.PATCH`, stored in [VERSION](VERSION) and bumped with `scripts/bump_version.py`:

- `PATCH` increments by 1 each bump, up to 20; the step past 20 wraps it to 0 and increments `MINOR`.
- `MINOR` increments up to 10; the step past 10 wraps it to 0 and increments `MAJOR`.
- `MAJOR` has no ceiling.

## Running

```bash
python3 main.py
```

(Packaging into a standalone `.app` via PyInstaller is a later step, not required for development.)
