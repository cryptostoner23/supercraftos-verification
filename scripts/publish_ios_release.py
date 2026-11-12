#!/usr/bin/env python3
"""Publish a verified unsigned release without deleting any existing signed apps."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def publish(source: Path, destination: Path):
    manifest=json.loads((source/'manifest.json').read_text())
    hashes=manifest.get('sha256',{})
    if not manifest.get('verified') or not manifest.get('build',{}).get('commit') or not hashes:
        raise ValueError('Release must include verification, source commit and artifact hashes')
    for name,digest in hashes.items():
        if Path(name).name != name or hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Artifact does not match release manifest: '+name)
    destination.mkdir(parents=True,exist_ok=True)
    assets={name:source/name for name in hashes}
    assets['SHA256SUMS']=source/'SHA256SUMS'
    assets['install.html']=ROOT/'ios_app_dist/ci_xcode/install.html'
    assets['FREE_APPLE_INSTALL.md']=ROOT/'docs/FREE_APPLE_INSTALL.md'
    for name in ['install_on_device.sh','supercraftos_install.sh']:
        assets[name]=ROOT/'scripts'/name
    if any(not path.is_file() for path in assets.values()):
        raise ValueError('Release assets or installation instructions are missing')
    assets['manifest.json']=source/'manifest.json' # update last
    for name,path in assets.items():
        fd,temporary=tempfile.mkstemp(prefix='.publish-',dir=destination)
        try:
            with os.fdopen(fd,'wb') as output, path.open('rb') as stream:
                shutil.copyfileobj(stream,output);output.flush();os.fsync(output.fileno())
            os.chmod(temporary,0o644)
            os.replace(temporary,destination/name)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
    return {'build':manifest['build'],'files':len(assets),'signing':manifest.get('signing')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'release/ios')
    parser.add_argument('--destination',type=Path,default=Path('/srv/ios-releases'))
    args=parser.parse_args()
    print(json.dumps(publish(args.source,args.destination),indent=2))
