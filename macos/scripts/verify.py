#!/usr/bin/env python3
"""Compile production engines with an isolated integration runner; no user media/settings touched."""
from pathlib import Path
import os,subprocess,tempfile,shutil
root=Path(__file__).resolve().parents[1]
env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
env['STOPFRAME_TEST_ROOT']=tempfile.mkdtemp(prefix='stopframe-verification-')
# The bundled helpers inherit the app sandbox. Standalone verification uses
# temporary ad-hoc copies without inheritance, leaving shipping helpers intact.
tools=Path(env['STOPFRAME_TEST_ROOT'])/'tools'
tools.mkdir()
for name in ['ffmpeg','ffprobe']:
    tool=tools/name
    shutil.copy2(root/'StopFrame/Resources/Tools'/name,tool)
    subprocess.run(['codesign','--force','--sign','-',str(tool)],check=True)
env['STOPFRAME_TOOLS']=str(tools)
files=[]
for folder in ['Models','Engine','Persistence','ViewModels']:
    files += sorted((root/'StopFrame'/folder).rglob('*.swift'))
files += [root/'StopFrame/AppState.swift',root/'Verification/main.swift']
exe=Path(env['STOPFRAME_TEST_ROOT'])/'verify'
subprocess.run(['xcrun','swiftc','-parse-as-library','-O','-o',str(exe),*[str(p) for p in files]],env=env,check=True)
subprocess.run([str(exe)],env=env,check=True)
print('Artifacts:',env['STOPFRAME_TEST_ROOT'])
