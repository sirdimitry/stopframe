![StopFrame — Find the frame worth keeping.](docs/branding/readme-banner.png)

# StopFrame

A local macOS app for turning video into sharp, distinct still images — with optional logo overlays and a manual timeline for the moments you want to choose yourself.

**навайбкодил- @sirdimitry** · [Version](VERSION) · [macOS build instructions](docs/BUILDING.md)

## What it does

- **Automatic selection:** scores sharpness, checks detected faces for open eyes and closed mouths, searches nearby moments to recover blinks, and skips visually similar frames. The requested 3–5 frames is a maximum: a static scene may produce one frame, and unsuitable footage may produce none.
- **Face checks:** checks both eyes and up to five detected faces. MediaPipe is included in the macOS build. If checking is unavailable, the app reports it and continues with sharpness and diversity. Detection is approximate; review your selections.
- **Timeline:** readable thumbnails with preserved proportions, capture markers, live preview, frame-by-frame navigation and capture with Space.
- **Logo overlays:** matches PNG templates from a folder to aspect/orientation/left-right slots. Captures default to the left slot; change side, aspect, offset and scale in review.
- **Review:** grouped screenshots, range/multiple selection, removal, zoomable detail view and optional HDR color correction.
- **Export:** full-resolution PNG or JPEG, configurable filename prefix, logo on/off and an explicitly chosen destination. Output goes into its `logo` subfolder.

## Install on Mac

Open the `StopFrame-<version>-macOS-arm64.dmg` installer and drag **StopFrame** into **Applications**.

The current build targets **Apple Silicon (M1 and newer), macOS 13 or later**. It is tested on the build Mac, not every supported OS version. Python is bundled; no Terminal setup is required to use the app.

The local build is ad-hoc signed, not Apple-notarized. macOS may require **System Settings → Privacy & Security → Open Anyway** after the first launch attempt. Intel builds and notarized distribution are not included in this release recipe.

## Run from source

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

Use Python 3.12 for the bundled MediaPipe face checks. With Python 3.13+, that optional dependency is skipped.

## Versioning

[VERSION](VERSION) is the single source for About, the macOS bundle metadata and the DMG filename. Editing code or making a Git commit **does not automatically change the version**.

To advance the version and create a release build:

```bash
.venv/bin/python scripts/build_macos.py --bump
```

To rebuild the same version, omit `--bump`. You can also run `scripts/bump_version.py` separately. The existing scheme is `MAJOR.MINOR.PATCH`: patch wraps after 20, minor after 10.

## Local processing

Video decoding, frame analysis, logo compositing and export happen on your Mac. No account or media upload is required. Settings, thumbnail cache and logs live under `~/Library/Application Support/StopFrame`. Logs can contain media filenames and error details; they are not transmitted by the app.

## Development

```bash
.venv/bin/python -B -m unittest discover -s tests -v
.venv/bin/python main.py --self-test
```

The app uses PySide6, OpenCV, NumPy, Pillow and optional MediaPipe. See [BUILDING.md](docs/BUILDING.md) for packaging and verification, and [branding prompts](docs/branding/PROMPTS.md) for the artwork sources.
