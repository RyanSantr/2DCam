"""Empacota o runtime em um EXE que o prepara uma unica vez. Windows 10/11."""
from pathlib import Path
import hashlib
import os
import re
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
bundle=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'dist/2DCamStudio'
output=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'dist'
version=re.search(r"VERSION = '([^']+)'",(root/'avatarcam/desktop/about.py').read_text()).group(1)
build=output/('launcher-build-'+version);build.mkdir(parents=True,exist_ok=True)
assert (bundle/'2DCamStudio.exe').is_file()
files=sorted(p for p in bundle.rglob('*') if p.is_file())
assert files and not any(p.is_symlink() for p in files)
payload=build/'payload.zip'
with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for file in files:archive.write(file,file.relative_to(bundle).as_posix())
with zipfile.ZipFile(payload) as archive:
    assert archive.testzip() is None
with payload.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
manifest=build/'files.txt';manifest.write_text('\n'.join(p.relative_to(bundle).as_posix() for p in files)+'\n',encoding='utf-8')
source=build/'StandaloneLauncher.cs';source.write_text((root/'scripts/StandaloneLauncher.cs').read_text(encoding='utf-8').replace('@@VERSION@@',version).replace('@@PAYLOAD_HASH@@',digest),encoding='utf-8-sig')
manifest_xml=build/'app.manifest';manifest_xml.write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"/></requestedPrivileges></security></trustInfo>
<compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1"><application><supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/></application></compatibility>
</assembly>''',encoding='utf-8')
framework=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319'
compiler=framework/'csc.exe'
if not compiler.is_file():raise SystemExit('Compilador do .NET Framework do Windows indisponivel.')
target=output/('2DCam-Studio-'+'.'.join(version.split('.')[:2])+'.exe')
command=[str(compiler),'/nologo','/target:winexe','/platform:x64','/optimize+', '/out:'+str(target),
         '/win32icon:'+str(root/'avatarcam/assets/studio.ico'),'/win32manifest:'+str(manifest_xml),
         '/resource:'+str(payload)+',2DCam.payload','/resource:'+str(manifest)+',2DCam.files',
         '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll',
         '/reference:'+str(framework/'System.IO.Compression.dll'),
         '/reference:'+str(framework/'System.IO.Compression.FileSystem.dll'),str(source)]
subprocess.run(command,check=True)
print('Executavel unico: '+str(target),flush=True)
print('Runtime: '+str(len(files))+' arquivos; SHA256 '+digest,flush=True)
