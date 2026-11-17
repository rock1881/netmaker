#!/usr/bin/env python3
"""Restore the original images without silently broadening active one-way ACLs."""
import json
from pathlib import Path
import sqlite3
import subprocess

BASE=Path('/root/netmaker-acl-direction-20261117')
conn=sqlite3.connect('file:/var/lib/docker/volumes/root_sqldata/_data/netmaker.db?mode=ro',uri=True)
for (value,) in conn.execute('SELECT value FROM acls'):
    a=json.loads(value)
    if a.get('enabled') and a.get('policy_type')=='device-policy' and a.get('allowed_traffic_direction')==0:
        raise SystemExit('Refusing rollback: active one-way ACL exists. Stock CE would convert it to two-way on startup.')
text=(BASE/'backup/compose-immediately-before-deploy.yml').read_text()
text=text.replace('gravitl/netmaker:$SERVER_IMAGE_TAG','local/netmaker:rollback-20261117')
text=text.replace('gravitl/netmaker-ui:$UI_IMAGE_TAG','local/netmaker-ui:rollback-20261117')
Path('/root/docker-compose.yml').write_text(text)
subprocess.run(['docker','compose','-f','/root/docker-compose.yml','up','-d','--no-deps','netmaker','netmaker-ui'],check=True)
print('Original images restored; the database was not overwritten.')
