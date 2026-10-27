#!/usr/bin/env python3
"""Package the verified native app in the established StopFrame Finder layout."""
from pathlib import Path
import hashlib,plistlib,subprocess
import dmgbuild
from ds_store import DSStore
ROOT=Path(__file__).resolve().parents[2]
def main():
    version=(ROOT/'VERSION').read_text().strip()
    app=ROOT/'dist/StopFrame.app'
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    if info['CFBundleShortVersionString']!=version:raise RuntimeError('Build native app first; version mismatch')
    subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    destination=ROOT/'dist'/f'StopFrame-{version}-Native-macOS-arm64.dmg'
    pending=destination.with_name(destination.stem+'-pending.dmg')
    mounted={}
    def prepare(mount_point,options):
        mounted['path']=Path(mount_point)
        copied=mounted['path']/'StopFrame.app'
        subprocess.run(['xattr','-d','com.apple.FinderInfo',str(copied)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['codesign','--verify','--deep','--strict',str(copied)],check=True)
    def layout(event):
        if event.get('type')=='operation::finished' and event.get('operation')=='dsstore::create':
            with DSStore.open(str(mounted['path']/'.DS_Store'),'r+') as store:
                view=store['.']['icvp']
                for channel in ['Red','Green','Blue']:view['backgroundColor'+channel]=0.065
                store['.']['icvp']=view
    dmgbuild.build_dmg(str(pending),f'StopFrame {version} Native',settings_file=str(ROOT/'packaging/dmg_settings.py'),defines={'root':str(ROOT)},settings={'create_hook':prepare,'icon':str(ROOT/'assets/branding/StopFrame-N.icns')},callback=layout)
    subprocess.run(['hdiutil','verify',str(pending)],check=True)
    pending.replace(destination)
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.dmg.sha256').write_text(f'{digest}  {destination.name}\n')
    print(destination)
if __name__=='__main__':main()
