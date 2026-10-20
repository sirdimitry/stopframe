![StopFrame — Find the frame worth keeping.](docs/branding/readme-banner.png)

# StopFrame

[English](README.md) · [Русский](README.ru.md)

A local macOS app for turning video into sharp, distinct still images — with optional logo overlays and a manual timeline for the moments you want to choose yourself.

**навайбкодил- @sirdimitry** · [Version](VERSION) · [macOS build instructions](docs/BUILDING.md)

## What it does

- **Automatic selection:** scores sharpness, checks detected faces for open eyes and closed mouths, searches nearby moments to recover blinks, and skips visually similar frames. The requested 1–5 frames is a maximum: a static scene may produce one frame, and unsuitable footage may produce none.
- **Face checks:** Apple Vision on Apple Silicon, with supported Neural Engine stages on macOS 14+ and automatic scheduling on macOS 13. MediaPipe is bundled as a fallback. Both eyes and detected mouths are checked. If checking is unavailable, the app reports it and continues with sharpness and diversity. Detection is approximate; review your selections.
- **Performance:** AVFoundation decoding and 960-pixel proxies for analysis; 640-pixel card previews; two concurrent filmstrip, preview and export jobs per queue; bounded decoder threads; a 64 MiB overlay cache. Final exports keep the original resolution and decoder. Different analysis resolution/models can select different moments.
- **Timeline:** readable thumbnails with preserved proportions, capture markers, live preview, frame-by-frame navigation and capture with Space.
- **Logo overlays:** matches PNG templates from a folder to aspect/orientation/left-right slots. Captures default to the left slot; change side, aspect, offset and scale in review.
- **Logo library:** manage the folder in Settings → Logo Library, or click the compact status badge beside the Logo switch in review. Green indicates available templates; missing files are detected. Setup stays focused on video import and analysis. The window opens wider and remembers its size.
- **Review:** grouped screenshots, range/multiple selection, clockwise rotation in 90° steps, removal, zoomable detail view and optional HDR color correction. Rotation applies to selected frames and export; four clicks restore the original orientation. Logo templates follow portrait/landscape orientation and stay upright.
- **Detail preview:** adjust HDR correction, rotate 90° clockwise, switch the logo side and fine-tune its position/scale without closing the preview. Previous/Next buttons (Alt+Left/Right) follow the card order across videos. Edits immediately update the cards and export.
- **Export:** full-resolution PNG or JPEG, configurable filename prefix, logo on/off and an explicitly chosen destination. Output goes into its `logo` subfolder.
- **Export preferences:** the compact “Параметры” button beside the logo switch on the review/export tab opens prefix, filename position, format and JPEG quality controls. Changes are saved immediately; the first tab ends with automatic selection.
- **Fresh folder:** opening a folder replaces the source list, cancels previous analysis and clears old captured frames and previews. All settings and logo templates are kept. Adding files extends the current session. Previously exported files remain on disk.
- **Photos:** JPEG, PNG, WebP, TIFF, BMP and HEIC/HEIF (macOS) go straight to review, without video analysis or frame capture. EXIF orientation is respected. Photos in the 16:9 family use its landscape/portrait logo templates; all other proportions use 4:3 templates. Review, logo adjustments, rotation and export work as usual. Photos export beside their originals with the configured prefix and format, preserving the source name; an empty prefix uses `logo`. Existing files are never overwritten. Video exports still use the selected destination's `logo` subfolder.

## Try StopFrame

If you work with video, please give StopFrame a try: select stills from a whole folder, fine-tune moments on the timeline, rotate and review your picks, add your logo, and export full-resolution images. Everything runs locally on your Mac.

Download the latest installer from [GitHub Releases](https://github.com/sirdimitry/stopframe/releases), install it, and try it with your own footage. If StopFrame helps you, a **star on this repository** is a welcome way to support the project and help others discover it. Feedback is equally valuable: [report a bug or suggest a feature](https://github.com/sirdimitry/stopframe/issues), share the project with someone who might find it useful, or contribute an improvement. Thank you for trying it!

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

On Apple Silicon, build the optional native face helper with `.venv/bin/python scripts/build_native.py` before running from source. Release builds include it automatically. Compare the old and optimized analysis pipelines with `.venv/bin/python scripts/benchmark.py /path/to/videos --count 8`.

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
