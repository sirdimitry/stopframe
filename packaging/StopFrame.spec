# Reproducible arm64 macOS app; run via scripts/build_macos.py.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
version = (root / 'VERSION').read_text().strip()
datas = [(str(root / 'VERSION'), '.'),
         (str(root / 'assets' / 'branding' / 'app-icon.png'), 'assets/branding'),
         (str(root / 'assets' / 'branding' / 'banner.png'), 'assets/branding'),
         (str(root / 'stopframe' / 'ui' / 'theme'), 'stopframe/ui/theme'),
         (str(root / 'stopframe' / 'ui' / 'icons'), 'stopframe/ui/icons')]
datas += collect_data_files('mediapipe')
datas += [(str(root / 'packaging' / 'licenses'), 'licenses')]
for package in ('PySide6_Essentials', 'shiboken6', 'opencv-contrib-python',
                'mediapipe', 'numpy', 'Pillow', 'matplotlib', 'protobuf',
                'absl-py', 'attrs', 'flatbuffers', 'sounddevice', 'cffi',
                'contourpy', 'cycler', 'fonttools', 'kiwisolver', 'packaging',
                'pyparsing', 'python-dateutil', 'six', 'sentencepiece'):
    datas += copy_metadata(package)
hiddenimports = collect_submodules('mediapipe', filter=lambda name: not any(
    part in name.split('.') for part in ('test', 'tests')) and not name.endswith('_test'))
a = Analysis([str(root / 'main.py')], pathex=[str(root)], datas=datas,
             binaries=[(str(root / 'build/StopFrameFaceWorker'), 'native')],
             hiddenimports=hiddenimports,
             excludes=['tkinter', 'IPython', 'pytest', 'jax', 'jaxlib', 'tensorflow'],
             hooksconfig={'matplotlib': {'backends': ['Agg']}},
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StopFrame',
          debug=False, strip=False, upx=False, console=False,
          target_arch='arm64', codesign_identity=None,
          icon=str(root / 'assets' / 'branding' / 'StopFrame.icns'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='StopFrame')
app = BUNDLE(coll, name='StopFrame.app',
             icon=str(root / 'assets' / 'branding' / 'StopFrame.icns'),
             bundle_identifier='com.sirdimitry.stopframe', version=version,
             info_plist={
                 'CFBundleShortVersionString': version,
                 'CFBundleVersion': version,
                 'NSHighResolutionCapable': True,
                 'NSPrincipalClass': 'NSApplication',
                 'LSMinimumSystemVersion': '13.0',
                 'NSHumanReadableCopyright': 'навайбкодил- @sirdimitry',
                 'LSApplicationCategoryType': 'public.app-category.video',
             })
