# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_data_files
root = Path(SPECPATH)
datas = [(str(root/'avatarcam/assets'), 'avatarcam/assets'), (str(root/'avatarcam/web3d'), 'avatarcam/web3d')]
datas += collect_data_files('mediapipe')
datas += [(str(root/name), '.') for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.txt')]
datas += [(str(root/'third-party-licenses'), 'third-party-licenses')]
a = Analysis([str(root/'app.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['webrtcvad','_webrtcvad','mediapipe.tasks.python.vision.face_landmarker','SpoutGL'],
    hookspath=[str(root/'scripts/hooks')], hooksconfig={'matplotlib': {'backends': ['Agg']}},
    runtime_hooks=[], excludes=['jax','jaxlib','tensorflow','torch','IPython','pytest','PyQt5','PyQt6'],
    noarchive=False, optimize=0)
pyz = PYZ(a.pure)
options=dict(name='2DCamStudio', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, icon=str(root/'avatarcam/assets/studio.ico'),
    version=str(root/'version_info.txt'))
if os.environ.get('AVATARCAM_BUILD_ONEFILE') != '1':
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='2DCamStudio')
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], **options)
