import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.purge_blockchain_cache import purge


class CachePurgeTests(unittest.TestCase):
    def test_preserves_unknown_tables_rules_messages_and_sequences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript('''CREATE TABLE raw_transfers(value TEXT);
                INSERT INTO raw_transfers VALUES ('disposable chain data');
                CREATE TABLE brain_messages(id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT);
                INSERT INTO brain_messages VALUES (17,'keep this conversation');
                CREATE TABLE auto_rules(id TEXT PRIMARY KEY, body TEXT);
                INSERT INTO auto_rules VALUES ('rule','keep this rule');
                CREATE TABLE unknown_settings(id TEXT PRIMARY KEY, value BLOB) WITHOUT ROWID;
                INSERT INTO unknown_settings VALUES ('private',x'0001');
                CREATE INDEX by_content ON brain_messages(content);''')
            report = purge(path)
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM raw_transfers').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT content FROM brain_messages').fetchone()[0], 'keep this conversation')
                self.assertEqual(db.execute('SELECT value FROM unknown_settings').fetchone()[0], b'\0\1')
                self.assertEqual(db.execute('SELECT seq FROM sqlite_sequence WHERE name="brain_messages"').fetchone()[0], 17)
                self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
            self.assertEqual(report['preserved_tables']['auto_rules'], 1)

    def test_missing_path_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.sqlite'
            with self.assertRaises(ValueError): purge(path)
            self.assertFalse(path.exists())
