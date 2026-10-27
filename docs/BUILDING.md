# Native macOS build

StopFrame 0.1.0 is a Swift/SwiftUI application for Apple Silicon and macOS 14+. Python 3.12+ is used only for the build scripts, not by the installed app. Install full Xcode at `/Applications/Xcode.app`, including its macOS SDK. The project keeps both app sandboxing and Xcode user-script sandboxing enabled. No custom signing build phase is added.

From the repository root:

```bash
python3 macos/scripts/build_native.py
python3 macos/scripts/verify.py
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r macos/requirements-build.txt
.venv-build/bin/python macos/scripts/build_dmg.py
```

Use `DEVELOPER_DIR` to choose a different installed Xcode. The scripts use ad-hoc signing and require no Developer ID credentials. Apple notarization is not performed. Development tests and actual compatibility on every macOS release are separate checks.

## Outputs

- `dist/StopFrame.app` — Release configuration, sandboxed, ad-hoc signed.
- `dist/StopFrame-0.1.0-Native-macOS-arm64.dmg` and its `.dmg.sha256`.
- `build/native/` — Xcode DerivedData.
- `build/ffmpeg/ffmpeg-7.1.tar.xz` — exact FFmpeg source archive for redistribution with the release.
- `macos/StopFrame/Resources/Licenses/FFmpeg-BUILD.txt` — pinned source checksum and configure flags.

The DMG keeps the StopFrame artwork and an Applications shortcut. The recipe verifies its contents' signature before compression and runs `hdiutil verify` before replacing an existing image.

## Decoder bootstrap

`build_native.py` first invokes `build_ffmpeg.py`. That recipe downloads **FFmpeg 7.1** from `https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz` and verifies SHA-256:

```text
40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6
```

No source modifications or third-party codec dependencies are used. GPL, nonfree and network support are not enabled. System zlib supports PNG output. Matroska stream-copy output is retained for the verification fixture. Full license, source URL and configuration are included in the application. Decoder binaries are ignored by Git; the public release attaches their exact source archive and build configuration.

Helpers are signed with `app-sandbox` and `inherit` entitlements before Xcode packages them, allowing them to inherit the app's user-granted access. Their standalone execution is not the supported path. The verification runner makes temporary copies with ordinary ad-hoc signatures for its own isolated subprocess tests; shipping helpers are not modified.

## Xcode

After bootstrapping the decoders, open `macos/StopFrame.xcodeproj`, choose the StopFrame scheme and My Mac, then run ⌘R. `VERSION` is the release source of truth; the build script synchronizes the bundle's marketing version. The header reads the installed bundle version.

## Verification

`python3 macos/scripts/verify.py` compiles production engines with an integration runner and creates only synthetic media in a unique temporary directory. No user photos, video, settings or source projects are modified. It exercises image orientation, rotation, safe export, legacy JSON, selection and folder changes, native and fallback video paths, face-quality failure handling, duplicate suppression, large counts and HDR pixel processing.

For public releases, retain the checksum and source assets alongside the DMG. The old Python build recipe remains in [BUILDING-python.md](BUILDING-python.md); use tag `v0.0.19` for that historical release.
