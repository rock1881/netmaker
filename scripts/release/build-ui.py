#!/usr/bin/env python3
"""Build the direction selector on the reviewed upstream Netmaker UI image."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE='gravitl/netmaker-ui@sha256:405a587af73bab233f4406b3b1b876369d0b0bfdc2dedb308a537226a502a8ba'
p=argparse.ArgumentParser();p.add_argument('--tag',default='netmaker-ui:v1.7.0');args=p.parse_args()
here=Path(__file__).resolve().parent
patch=here/'patch-ui.py'
dockerfile=here/'Dockerfile.ui'
if not patch.exists():
 patch=here.parents[1]/'local/acl-direction/patch-ui.py'
 dockerfile=here.parents[1]/'local/acl-direction/Dockerfile.ui'
subprocess.run(['docker','pull','--platform','linux/amd64',BASE],check=True)
container=subprocess.check_output(['docker','create','--platform','linux/amd64',BASE],text=True).strip()
try:
 with tempfile.TemporaryDirectory(prefix='netmaker-ui-') as directory:
  d=Path(directory)
  subprocess.run(['docker','cp',container+':/usr/share/nginx/html/assets/index-DrhEsdGo.js',str(d/'original.js')],check=True)
  subprocess.run(['python3',str(patch),str(d/'original.js'),str(d/'index-acl-direction-5c0e5d0a.js')],check=True)
  shutil.copy2(dockerfile,d/'Dockerfile')
  subprocess.run(['docker','build','--platform','linux/amd64','-t',args.tag,str(d)],check=True)
finally:
 subprocess.run(['docker','rm',container],check=True,stdout=subprocess.DEVNULL)
print('Built',args.tag)
