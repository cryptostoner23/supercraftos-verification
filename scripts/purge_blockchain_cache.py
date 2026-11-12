"""Rebuild an OFFLINE Web3 state database without disposable blockchain caches.

Stop web3-agent before running. Rules, messages, transaction logs and all unknown
application tables are copied and compared byte for byte before replacement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

CACHE_TABLES = frozenset({'raw_transfers', 'raw_swaps', 'liquidity_pools',
                          'ingest_cursor', 'token_meta', 'intel_sync'})


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def digest(connection, table):
    checksum = hashlib.sha256()
    count = 0
    columns = [row[1] for row in connection.execute('PRAGMA table_info(' + quote(table) + ')')]
    order = ','.join(quote(column) for column in columns)
    for row in connection.execute('SELECT * FROM ' + quote(table) + ' ORDER BY ' + order):
        checksum.update(repr(tuple(row)).encode()); checksum.update(b'\n'); count += 1
    return count, checksum.hexdigest()


def purge(path):
    path = Path(path).resolve()
    if not path.is_file(): raise ValueError('Database does not exist')
    # Refuse to rebuild a database any other process has open. On Linux the
    # process table is visible under /proc; on non-Linux platforms there is no
    # /proc, so the open-file check is skipped (the WAL checkpoint below still
    # refuses a busy database).
    proc = Path('/proc')
    if proc.is_dir():
        for process in proc.iterdir():
            if not process.name.isdigit() or int(process.name) == os.getpid(): continue
            try:
                for descriptor in (process / 'fd').iterdir():
                    if descriptor.resolve() == path:
                        raise RuntimeError('Stop all processes using the database before purging')
            except (FileNotFoundError, PermissionError): pass
    source = sqlite3.connect(str(path), timeout=5)
    if source.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
        source.close(); raise RuntimeError('Database is still busy')
    size_before = path.stat().st_size
    fd, temporary = tempfile.mkstemp(prefix='.state-clean-', suffix='.sqlite', dir=path.parent)
    os.close(fd)
    candidate = Path(temporary)
    target = sqlite3.connect(str(candidate))
    retained = {}
    try:
        schema = list(source.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC"))
        tables = [(name, sql) for kind, name, _, sql in schema if kind == 'table' and name != 'sqlite_sequence']
        for name, sql in tables:
            target.execute(sql)
            if name not in CACHE_TABLES:
                rows = source.execute('SELECT * FROM ' + quote(name))
                columns = len(rows.description)
                target.executemany('INSERT INTO ' + quote(name) + ' VALUES (' + ','.join('?' for _ in range(columns)) + ')', rows)
                retained[name] = digest(source, name)
        if source.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
            target.execute('DELETE FROM sqlite_sequence')
            target.executemany('INSERT INTO sqlite_sequence VALUES (?,?)', source.execute('SELECT * FROM sqlite_sequence'))
        for kind, _, _, sql in schema:
            if kind != 'table': target.execute(sql)
        target.commit()
        assert target.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        for table, expected in retained.items():
            assert digest(target, table) == expected, 'Preserved table mismatch: ' + table
        for table, _ in tables:
            if table in CACHE_TABLES:
                assert target.execute('SELECT count(*) FROM ' + quote(table)).fetchone()[0] == 0
        target.close(); source.close()
        with candidate.open('rb') as handle: os.fsync(handle.fileno())
        candidate.chmod(0o600)
        os.replace(candidate, path)
        for suffix in ['-wal', '-shm']: Path(str(path) + suffix).unlink(missing_ok=True)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return {'before_bytes': size_before, 'after_bytes': path.stat().st_size,
                'preserved_tables': {name: value[0] for name, value in retained.items()},
                'cleared_tables': sorted(CACHE_TABLES)}
    finally:
        source.close(); target.close(); candidate.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    print(json.dumps(purge(args.database), indent=2))
