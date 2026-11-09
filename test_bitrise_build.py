"""Recorded checkout metadata must identify the source that actually built."""
import unittest
from scripts.bitrise_build import cloned_commit

class CheckoutIdentityTests(unittest.TestCase):
    def test_reads_actual_clone_export(self):
        self.assertEqual(cloned_commit('=> GIT_CLONE_COMMIT_HASH\n   value: ' + 'a'*40 + '\n'), 'a'*40)

    def test_unrelated_hash_or_missing_export_is_not_evidence(self):
        for log in ['git checkout ' + 'a'*40, '=> GIT_CLONE_COMMIT_HASH\n   value: unknown\n']:
            self.assertIsNone(cloned_commit(log))

    def test_conflicting_clone_exports_fail_closed(self):
        log=''.join('=> GIT_CLONE_COMMIT_HASH\n   value: '+sha*40+'\n' for sha in ('a','b'))
        self.assertIsNone(cloned_commit(log))

if __name__ == '__main__': unittest.main()
