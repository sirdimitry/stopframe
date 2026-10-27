#!/usr/bin/env python3
"""Build pinned, offline-at-runtime FFmpeg helpers from their exact upstream sources."""
from pathlib import Path
import hashlib,os,platform,shutil,subprocess,tarfile,urllib.request
ROOT=Path(__file__).resolve().parents[2]
VERSION='7.1'
SHA256='40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6'
FLAGS=['--prefix=/usr/local','--cc=/usr/bin/clang','--arch=arm64','--target-os=darwin',
       '--disable-autodetect','--disable-network','--disable-doc','--disable-ffplay','--disable-debug','--enable-small',
       '--enable-zlib','--disable-encoders','--enable-encoder=png','--disable-muxers','--enable-muxer=image2pipe',
       '--enable-muxer=matroska','--disable-filters','--enable-filter=scale','--enable-filter=format',
       '--disable-protocols','--enable-protocol=file','--enable-protocol=pipe','--disable-videotoolbox',
       '--extra-cflags=-mmacosx-version-min=14.0','--extra-ldflags=-mmacosx-version-min=14.0']
HELPER_ENTITLEMENTS='''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>com.apple.security.app-sandbox</key><true/>
<key>com.apple.security.inherit</key><true/></dict></plist>'''
def build():
    if platform.machine()!='arm64': raise SystemExit('This recipe targets Apple Silicon.')
    cache=ROOT/'build/ffmpeg';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/f'ffmpeg-{VERSION}.tar.xz'
    if not archive.exists():
        with urllib.request.urlopen(f'https://ffmpeg.org/releases/ffmpeg-{VERSION}.tar.xz',timeout=60) as r:
            archive.write_bytes(r.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256: raise RuntimeError('FFmpeg source checksum mismatch')
    source=cache/f'ffmpeg-{VERSION}'
    if not source.exists():
        with tarfile.open(archive) as tar: tar.extractall(cache,filter='data')
    config='\n'.join(FLAGS)+'\n'
    stamp=cache/'recipe.txt'
    if not stamp.exists() or stamp.read_text()!=config:
        subprocess.run(['./configure',*FLAGS],cwd=source,check=True)
        stamp.write_text(config)
    subprocess.run(['make',f'-j{min(6,os.cpu_count() or 2)}'],cwd=source,check=True)
    tools=ROOT/'macos/StopFrame/Resources/Tools';tools.mkdir(parents=True,exist_ok=True)
    entitlements=cache/'Helper.entitlements';entitlements.write_text(HELPER_ENTITLEMENTS)
    for name in ['ffmpeg','ffprobe']:
        shutil.copy2(source/name,tools/name)
        subprocess.run(['codesign','--force','--sign','-','--entitlements',str(entitlements),str(tools/name)],check=True)
    licenses=ROOT/'macos/StopFrame/Resources/Licenses';licenses.mkdir(parents=True,exist_ok=True)
    for name in ['COPYING.LGPLv2.1','LICENSE.md']:
        shutil.copy2(source/name,licenses/name)
    (licenses/'FFmpeg-BUILD.txt').write_text(f'FFmpeg {VERSION}\nSource: https://ffmpeg.org/releases/ffmpeg-{VERSION}.tar.xz\nSHA-256: {SHA256}\n\nConfiguration:\n'+config)
    return tools
if __name__=='__main__': print(build())
