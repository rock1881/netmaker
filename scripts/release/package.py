#!/usr/bin/env python3
"""Package a strict list of public release assets; no deployment backups."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import tarfile

p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--version',default='v1.7.0');args=p.parse_args()
assert re.fullmatch(r'v\d+\.\d+\.\d+',args.version),'Use the original semantic version, without a suffix'
root=Path(__file__).resolve().parents[2];args.output.mkdir(parents=True,exist_ok=True)

def archive(name,entries):
 with tarfile.open(args.output/name,'w:gz') as archive:
  for target,source in entries.items():
   data=source.read_bytes();info=tarfile.TarInfo(target);info.size=len(data)
   info.mode=0o755 if target=='netmaker' or target.endswith('.py') else 0o644
   info.mtime=0;archive.addfile(info,io.BytesIO(data))

archive(f'netmaker-{args.version}-linux-amd64.tar.gz',{'netmaker':args.binary,'LICENSE.md':root/'LICENSE.md','README.md':root/'scripts/release/README.md'})
archive(f'netmaker-ui-{args.version}-patch.tar.gz',{'build-ui.py':root/'scripts/release/build-ui.py','patch-ui.py':root/'local/acl-direction/patch-ui.py','Dockerfile.ui':root/'local/acl-direction/Dockerfile.ui','README.md':root/'scripts/release/README.md'})
files=sorted(args.output.glob('*.tar.gz'))
(args.output/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+f.name+'\n' for f in files))
print('\n'.join(str(f) for f in files))
