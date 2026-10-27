#!/usr/bin/env python3
"""Build the native, sandboxed Apple Silicon application with local ad-hoc signing."""
from pathlib import Path
import os,plistlib,re,shutil,subprocess
from build_ffmpeg import build
ROOT=Path(__file__).resolve().parents[2]
def main():
    build()
    version=(ROOT/'VERSION').read_text().strip()
    project=ROOT/'macos/StopFrame.xcodeproj/project.pbxproj'
    project.write_text(re.sub(r'MARKETING_VERSION = [^;]+;',f'MARKETING_VERSION = {version};',project.read_text()))
    env=dict(os.environ)
    if 'DEVELOPER_DIR' not in env:
        env['DEVELOPER_DIR']='/Applications/Xcode.app/Contents/Developer'
    derived=ROOT/'build/native'
    subprocess.run(['xcodebuild','-project',str(project.parent),'-scheme','StopFrame','-configuration','Release',
                    '-derivedDataPath',str(derived),'CLANG_ENABLE_STAT_CACHE=NO','CODE_SIGN_IDENTITY=-','CODE_SIGN_STYLE=Manual','build'],env=env,check=True)
    built=derived/'Build/Products/Release/StopFrame.app'
    info=plistlib.loads((built/'Contents/Info.plist').read_bytes())
    if info['CFBundleShortVersionString']!=version:raise RuntimeError('App version mismatch')
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    app=out/'StopFrame Native (N).app'
    if app.exists():shutil.rmtree(app)
    shutil.copytree(built,app,symlinks=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    print('Native application:',app)
if __name__=='__main__':main()
