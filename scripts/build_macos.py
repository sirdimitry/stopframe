#!/usr/bin/env python3
"""Build StopFrame.app + branded DMG. --bump advances VERSION once before building."""
import argparse
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bump', action='store_true', help='Advance the release version before building')
    parser.add_argument('--skip-app', action='store_true', help='Rebuild only the DMG from the verified app')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('This recipe builds on an Apple Silicon Mac.')
    if args.bump and args.skip_app:
        parser.error('--bump requires rebuilding the app')
    if args.bump:
        run(sys.executable, 'scripts/bump_version.py')
    version = (ROOT / 'VERSION').read_text().strip()
    iconset = ROOT / 'build' / 'StopFrame.iconset'
    iconset.mkdir(parents=True, exist_ok=True)
    if not args.skip_app:
        run(sys.executable, 'scripts/build_native.py')
        for size in (16, 32, 128, 256, 512):
            for multiplier in (1, 2):
                suffix = '@2x' if multiplier == 2 else ''
                pixels = size * multiplier
                run('sips', '-z', pixels, pixels, ROOT / 'assets/branding/app-icon.png',
                    '--out', iconset / f'icon_{size}x{size}{suffix}.png')
        run('iconutil', '-c', 'icns', iconset, '-o', ROOT / 'assets/branding/StopFrame.icns')
        run(sys.executable, '-m', 'PyInstaller', '--noconfirm', 'packaging/StopFrame.spec')
    app = ROOT / 'dist' / 'StopFrame.app'
    run('codesign', '--verify', '--deep', '--strict', app)
    import plistlib
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info['CFBundleShortVersionString'] != version:
        raise RuntimeError('App version differs from VERSION; rebuild the app first.')
    run(app / 'Contents/MacOS/StopFrame', '--self-test')
    dmg = ROOT / 'dist' / f'StopFrame-{version}-macOS-arm64.dmg'
    # Build to a new temporary name; preserve any previous installer on failure.
    pending = ROOT / 'dist' / f'StopFrame-{version}-pending.dmg'
    import dmgbuild
    from ds_store import DSStore
    mounted = {}

    def prepare_volume(mount_point, options):
        mounted['path'] = Path(mount_point)
        copied_app = mounted['path'] / 'StopFrame.app'
        # Finder flags on a copied bundle root are not signature-safe. Strip only
        # this display attribute from our generated copy, never from user files.
        subprocess.run(['xattr', '-d', 'com.apple.FinderInfo', str(copied_app)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        run('codesign', '--verify', '--deep', '--strict', copied_app)

    def finish_layout(event):
        if event.get('type') == 'operation::finished' and event.get('operation') == 'dsstore::create':
            # Finder otherwise assumes a white background even for a dark image,
            # making filenames almost invisible. Keep the matching fallback color.
            with DSStore.open(str(mounted['path'] / '.DS_Store'), 'r+') as store:
                view = store['.']['icvp']
                for channel in ('Red', 'Green', 'Blue'):
                    view['backgroundColor' + channel] = 0.065
                store['.']['icvp'] = view

    dmgbuild.build_dmg(str(pending), f'StopFrame {version}',
                       settings_file=str(ROOT / 'packaging/dmg_settings.py'), defines={'root': str(ROOT)},
                       settings={'create_hook': prepare_volume}, callback=finish_layout)
    run('hdiutil', 'verify', pending)
    pending.replace(dmg)
    with dmg.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    dmg.with_suffix('.dmg.sha256').write_text(f'{digest}  {dmg.name}\n')
    print(f'\nReady: {dmg}')


if __name__ == '__main__':
    main()
