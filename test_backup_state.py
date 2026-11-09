import sqlite3
import tarfile
import tempfile
from pathlib import Path
import unittest
from scripts.backup_state import backup

class StateBackupTests(unittest.TestCase):
    def test_wal_backup_restores_committed_data_and_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir()
            outside=root/'private';outside.write_text('outside-secret')
            (data/'escape').symlink_to(outside)
            (data/'access.key').write_text('test-access-key')
            with sqlite3.connect(data/'jobs.sqlite3') as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('CREATE TABLE evidence(value TEXT)')
                db.execute("INSERT INTO evidence VALUES('verified')");db.commit()
                archive=backup(data,root/'backups',keep=1)
                self.assertEqual(archive.stat().st_mode & 0o777,0o600)
                with tarfile.open(archive) as tar:
                    self.assertNotIn('data/escape',tar.getnames())
                    tar.extractall(root/'restore',filter='data')
                with sqlite3.connect(root/'restore/data/jobs.sqlite3') as restored:
                    self.assertEqual(restored.execute('SELECT value FROM evidence').fetchone()[0],'verified')
                newer=backup(data,root/'backups',keep=1)
                self.assertFalse(archive.exists());self.assertTrue(newer.exists())
            with self.assertRaises(ValueError):backup(data,data/'backups')
