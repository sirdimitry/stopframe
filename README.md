![StopFrame — Find the frame worth keeping.](docs/branding/readme-banner.png)

# StopFrame — native macOS app

[English](README.md) · [Русский](README.ru.md)

**StopFrame 0.1.0 is a native macOS application written in Swift and SwiftUI.** It uses AVFoundation, Apple Vision, Core Image and ImageIO to find sharp, distinct video frames, process photographs, add logo overlays and export images at their original resolution. Python, Qt and MediaPipe are not required by the native app.

The native version carries forward the workflows of Python release 0.0.19. Everything runs locally: no account, media uploads or network connection is needed for processing.

**Created by @sirdimitry** · [Version](VERSION) · [Download for macOS](https://github.com/sirdimitry/stopframe/releases/latest) · [Build instructions](docs/BUILDING.md)

## Install

Download **StopFrame-0.1.0-Native-macOS-arm64.dmg** from [GitHub Releases](https://github.com/sirdimitry/stopframe/releases/latest), open it and drag **StopFrame** into **Applications**.

Requirements: **Apple Silicon (M1 or newer), macOS 14 or later**. The application interface is currently in Russian. The build is ad-hoc signed and is not notarized by Apple; macOS may offer **System Settings → Privacy & Security → Open Anyway** after the first launch attempt. System security settings are not changed by the installer. Intel and older macOS builds are not included.

## Features

- **Video and photo import:** open a folder, add files, or drag mixed batches into the window. Opening a folder cancels analysis and replaces the session while retaining settings and logo templates. Adding files extends the session.
- **Automatic frame selection:** choose any positive maximum count. Requests above 99 require confirmation. Sharpness filtering, time coverage, face checks, nearby-frame recovery for blinks, and spatial duplicate detection prioritize usable, distinct images. A static scene can yield one frame; unsuitable footage can yield none.
- **Native face checks:** Apple Vision checks all detected faces, both available eye regions and detected mouths. If unavailable, the app warns and continues using sharpness and diversity. Face analysis is approximate; review the result. Native decoding and landmark topology can produce different selected moments from Python/OpenCV.
- **Manual timeline:** filmstrips, capture markers, live preview, Left/Right frame stepping, and Space to capture.
- **Photographs:** JPEG, PNG, WebP, TIFF, BMP and HEIC/HEIF go straight to review, respecting EXIF orientation. Photos outside the 16:9 family use 4:3 logo templates.
- **Review:** groups by source, Cmd/Shift selection, select all, batch exclusion, 90° clockwise rotation and optional HLG-to-Rec.709 color correction. Four rotations restore the original orientation; logos remain upright.
- **Detail view:** Previous/Next across groups (Option+Left/Right), zoom and pan, HDR correction, rotation, logo side/aspect, drag or arrow-key positioning, exact offset/scale fields and reset. Edits immediately apply to cards and export. Labels stay on one line and logo choices fill the available width.
- **Logo library:** PNG template matching by aspect, orientation and side; Settings and a review-toolbar shortcut; rescan to detect missing files; a 64 MiB decoded-logo cache.
- **Export:** full-resolution PNG or JPEG, filename prefix before/after the name, JPEG quality and logo switch. Preferences live in a compact panel in review. Video frames go into the chosen folder's `logo` subfolder. Photos save beside their originals with their source name and a prefix (`logo` when blank). Atomic name reservation prevents overwriting originals or existing exports. The macOS sandbox asks for access to photo source folders when creating adjacent files.
- **Native workspace:** SwiftUI controls, explicit empty/busy/error states, cancellation, accessible labels, keyboard actions, reduced-motion support and persistent session/settings.

AVFoundation is the primary decoder. Bundled, independently built **FFmpeg/ffprobe 7.1** provide a local fallback for unsupported containers/codecs such as some AVI/MKV files. They do not depend on Homebrew. The release includes the exact FFmpeg source archive, build configuration and LGPL notices.

## Build and verify

```bash
python3 macos/scripts/build_native.py
python3 macos/scripts/verify.py
```

The first command prepares the decoder, builds and signs `StopFrame.app`. Then open `macos/StopFrame.xcodeproj` in Xcode, choose **StopFrame → My Mac**, and run with ⌘R. To create the installer:

```bash
python3 macos/scripts/build_dmg.py
```

See [BUILDING.md](docs/BUILDING.md) for outputs, source checksums and signing details. Integration checks use generated media and separate temporary settings. Coverage includes EXIF, rotation, PNG/JPEG exports, collision protection, legacy JSON, folder resets, MP4/MKV, large selection counts, duplicate rejection, unavailable/bad face checks, HDR pixels and error reporting. Full testing across every supported OS, camera/HDR format, and VoiceOver configuration remains incomplete.

## Local data

The native app uses the macOS sandbox with user-selected file access and persistent security-scoped bookmarks. Settings and session data are stored in its container under `~/Library/Containers/SD.StopFrame/Data/Library/Application Support/StopFrame`; caches remain local. Logs can contain media filenames and error details; the app does not transmit them. The native app does not automatically migrate the Python app's settings or media session.

## Previous Python version

The root `stopframe/`, `main.py`, `tests/` and Python packaging scripts remain available as legacy source. Version **0.0.19** and its installer remain in [release history](https://github.com/sirdimitry/stopframe/releases/tag/v0.0.19). Python build notes are preserved in [BUILDING-python.md](docs/BUILDING-python.md). The current installer is the native Swift application.

If StopFrame is useful, please star the repository or [report a bug or suggest a feature](https://github.com/sirdimitry/stopframe/issues).
