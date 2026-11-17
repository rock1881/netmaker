#!/usr/bin/env python3
"""Run as root on us1-pub after uploading release/ next to backup/."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

BASE=Path('/root/netmaker-acl-direction-20261117')
RELEASE=BASE/'release'
COMPOSE=Path('/root/docker-compose.yml')
IMAGES={'netmaker':'local/netmaker:v1.7.0-acl-direction-20261117',
        'netmaker-ui':'local/netmaker-ui:v1.7.0-acl-direction-20261117'}

def cmd(args):
    p=subprocess.run(args,text=True,capture_output=True)
    if p.returncode:raise RuntimeError(f'{args[0:3]}: {p.stderr[-2000:]} {p.stdout[-2000:]}')
    return p.stdout

def inspect(name):return json.loads(cmd(['docker','inspect',name]))[0]

def policies():
    p=inspect('netmaker');env=dict(x.split('=',1) for x in p['Config']['Env'])
    ip=p['NetworkSettings']['Networks']['root_default']['IPAddress']
    r=urllib.request.Request('http://'+ip+':8081/api/v1/acls?network=netmaker',headers={'Authorization':'Bearer '+env['MASTER_KEY']})
    with urllib.request.urlopen(r,timeout=5) as f:
        value=json.load(f)
    return sorted(value['Response'],key=lambda a:a['id'])

if __name__=='__main__':
    manifest=json.loads((RELEASE/'sha256.json').read_text())
    for name,digest in manifest.items():assert hashlib.sha256((RELEASE/name).read_bytes()).hexdigest()==digest,name
    recorded=json.loads((BASE/'backup/images.json').read_text())
    for name in IMAGES:assert inspect(name)['Image']==recorded[name]['image'],'Unexpected running image: '+name
    before=policies()
    (BASE/'backup/policies-before-deploy.json').write_text(json.dumps(before,indent=2))
    caddy_hash=hashlib.sha256(Path('/root/Caddyfile').read_bytes()).hexdigest()
    original=COMPOSE.read_text()
    patched=original
    for name,old in [('netmaker','gravitl/netmaker:$SERVER_IMAGE_TAG'),('netmaker-ui','gravitl/netmaker-ui:$UI_IMAGE_TAG')]:
        assert patched.count('image: '+old)==1
        patched=patched.replace('image: '+old,'image: '+IMAGES[name])
        rollback='local/'+name+':rollback-20261117'
        cmd(['docker','tag',recorded[name]['image'],rollback])
    for service,dockerfile in [('netmaker','Dockerfile.server'),('netmaker-ui','Dockerfile.ui')]:
        output=cmd(['docker','build','--pull=false','-f',str(RELEASE/dockerfile),'-t',IMAGES[service],str(RELEASE)])
        (BASE/(service+'-image-build.log')).write_text(output)
    pending=COMPOSE.with_name('docker-compose.acl-direction.pending.yml')
    pending.write_text(patched);os.chmod(pending,0o600)
    cmd(['docker','compose','--project-name','root','--env-file','/root/netmaker.env','-f',str(pending),'config','--quiet'])
    snapshot=BASE/'backup/compose-immediately-before-deploy.yml'
    assert not snapshot.exists(),'Already deployed; use a new release directory'
    shutil.copy2(COMPOSE,snapshot)
    switched=False
    try:
        os.replace(pending,COMPOSE);switched=True
        cmd(['docker','compose','-f',str(COMPOSE),'up','-d','--no-deps','netmaker','netmaker-ui'])
        for _ in range(30):
            try:
                after=policies()
                break
            except Exception:time.sleep(1)
        else:raise RuntimeError('Netmaker API did not become ready')
        assert before==after,'ACL policies changed unexpectedly'
        assert caddy_hash==hashlib.sha256(Path('/root/Caddyfile').read_bytes()).hexdigest()
        sha=cmd(['docker','exec','netmaker','sha256sum','/root/netmaker']).split()[0]
        assert sha==manifest['netmaker']
        ui=inspect('netmaker-ui');ip=ui['NetworkSettings']['Networks']['root_default']['IPAddress']
        with urllib.request.urlopen('http://'+ip+'/',timeout=5) as f:index=f.read()
        asset='index-acl-direction-5c0e5d0a.js'
        assert asset.encode() in index
        with urllib.request.urlopen('http://'+ip+'/assets/'+asset,timeout=5) as f:data=f.read()
        assert hashlib.sha256(data).hexdigest()==manifest[asset]
        assert data.count(b'"aria-label":"Traffic direction"')==2
        assert cmd(['systemctl','is-active','netclient']).strip()=='active'
        (BASE/'deployment-result.json').write_text(json.dumps({'images':IMAGES,'binary_sha256':sha,'policies_unchanged':True,'caddy_unchanged':True,'ui_direction_selectors':2},indent=2))
        print('PASS: new server binary, authenticated API, unchanged policies, unchanged Caddy, UI selectors, active netclient')
    except Exception:
        if switched:
            shutil.copy2(snapshot,COMPOSE)
            cmd(['docker','compose','-f',str(COMPOSE),'up','-d','--no-deps','netmaker','netmaker-ui'])
        raise
