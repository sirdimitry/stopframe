# macOS packaging

Build on an Apple Silicon Mac with Python 3.12. The recipe targets arm64, not universal2. Qt in this build requires macOS 13+; actual compatibility should be checked on each OS you intend to support.

```bash
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build_macos.py
```

Outputs:

- `dist/StopFrame.app`
- `dist/StopFrame-<VERSION>-macOS-arm64.dmg`
- matching `.dmg.sha256` checksum

`--bump` increments VERSION before the build. Failed builds do not roll it back: rerun without `--bump` after fixing the issue. `--skip-app` rebuilds the DMG from an existing app and refuses mismatched app/version metadata. Existing installers are replaced only after the new image passes verification.

## Contents and checks

The PyInstaller recipe includes the Python runtime, Qt, OpenCV, MediaPipe model data, theme, icons, banner and VERSION. It compiles `native/FaceWorker.swift` with the Xcode Command Line Tools and bundles the signed arm64 Apple Vision helper. No external Python or model downloads are needed. MediaPipe remains a fallback through the bundled executable's `--face-worker` mode.

Before creating the DMG, the script verifies the bundle signature and runs `--self-test` on the bundled executable: About/version/resources, synthetic video decoding, filmstrip rendering, full-resolution PNG export with transparency, MediaPipe fallback, native landmark geometry and threaded Automatic Pick through Apple Vision. It reports the selected compute backend. The test uses generated media in a temporary directory and does not read or overwrite user settings. The disk image is then verified with `hdiutil`.

For a QA capture of the About panel:

```bash
STOPFRAME_QA_DIR=/tmp/stopframe-qa dist/StopFrame.app/Contents/MacOS/StopFrame --self-test
```

The DMG uses the app icon as its volume icon, a graphite/coral background, and positioned app/Applications icons. `dmgbuild` writes Finder layout data without requiring Finder automation.

## Signing

This recipe uses PyInstaller's ad-hoc signing. No Developer ID certificate or notarization credentials are stored in the repository. A public notarized release requires the owner's Apple Developer signing identity and a separate notarization/stapling step. No Gatekeeper settings are changed by this build.

## References

- [PyInstaller runtime resources and bundled executable behavior](https://pyinstaller.org/en/stable/runtime-information.html)
- [dmgbuild layout and icon settings](https://dmgbuild.readthedocs.io/en/latest/example.html)
