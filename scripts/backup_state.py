"""Create a private WAL-aware state backup with bounded retention."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import sqlite3
import tarfile
import tempfile


def backup(source: Path, destination: Path, *, keep=7, environment: Path | None = None):
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir() or destination == source or source in destination.parents:
        raise ValueError('Backup destination must be outside the state directory')
    if type(keep) is not int or not 1 <= keep <= 90:
        raise ValueError('Retention must be 1 to 90 backups')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    name = 'supercraftos-state-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.tar.gz'
    with tempfile.TemporaryDirectory(prefix='.backup-', dir=destination) as temporary:
        stage = Path(temporary)/'state'; stage.mkdir(mode=0o700)
        databases = []
        for path in source.rglob('*'):
            if path.is_symlink():
                continue  # Never follow workspace symlinks outside the data boundary.
            target = stage/path.relative_to(source)
            if path.is_dir(): target.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                if path.name.endswith(('-wal', '-shm')): continue
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with path.open('rb') as stream: sqlite = stream.read(16) == b'SQLite format 3\x00'
                    if sqlite: databases.append((path, target))
                    else: shutil.copyfile(path, target)
                except FileNotFoundError:
                    continue  # Temporary atomic-write files can disappear during a backup.
        for path, target in databases:
            with sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=30) as src, sqlite3.connect(target) as dst:
                src.backup(dst)
        if environment is not None:
            shutil.copyfile(environment, Path(temporary)/'supercraftos.env')
        candidate = Path(temporary)/name
        with tarfile.open(candidate, 'w:gz') as archive:
            archive.add(stage, arcname='data', recursive=True)
            if environment is not None: archive.add(Path(temporary)/'supercraftos.env', arcname='supercraftos.env')
        candidate.chmod(0o600)
        with tarfile.open(candidate) as archive:
            if not archive.getmembers(): raise RuntimeError('Empty state archive')
        result=destination/name
        candidate.replace(result)
    for stale in sorted(destination.glob('supercraftos-state-*.tar.gz'), reverse=True)[keep:]: stale.unlink()
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1]/'data')
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--environment', type=Path)
    parser.add_argument('--keep', type=int, default=7)
    args=parser.parse_args()
    os.umask(0o077)
    print(backup(args.source,args.destination,keep=args.keep,environment=args.environment))
