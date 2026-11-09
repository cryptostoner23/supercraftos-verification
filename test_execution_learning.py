import tempfile
from pathlib import Path
import unittest
from execution_learning import memory_view, public_text, practices
from job_store import JobStore

class LearningTests(unittest.TestCase):
    def test_only_completed_results_contribute_retrievable_lessons(self):
        with tempfile.TemporaryDirectory() as d:
            store = JobStore(Path(d)/'jobs.db')
            job = store.submit('Repair a failing parser')
            with self.assertRaises(ValueError): store.remember(job['id'], 'Check invalid input')
            store.claim('worker')
            store.finish(job['id'], 'worker', 'completed', {'checks': [{'exit_code': 1}, {'exit_code': 0}],
                'review': {'accepted': True}, 'files': [{'path': 'parser.py', 'sha256': 'abc'}]})
            store.remember(job['id'], 'Run malformed-input tests. API_KEY=never-keep-this')
            view = memory_view(store)
            self.assertFalse(view['model_weights_trained'])
            self.assertEqual(view['lessons'][0]['checks_passed'], 1)
            self.assertTrue(view['lessons'][0]['accepted'])
            self.assertNotIn('never-keep-this', str(view))
            self.assertEqual(view['lessons'][0]['job_id'], job['id'])
            self.assertTrue(store.forget_lesson(view['lessons'][0]['id']))
            self.assertEqual(store.lessons(), [])

    def test_public_explanations_strip_credentials_not_evidence(self):
        value = public_text('Tests passed. Bearer abc-secret TOKEN=secret https://example.test/path?token=hidden#secret')
        self.assertIn('Tests passed.', value)
        for secret in ['abc-secret', 'TOKEN=secret', 'token=hidden', '#secret']: self.assertNotIn(secret, value)
        self.assertIn('https://example.test/path', value)
        self.assertEqual(practices('deployment packaging fresh installation')[0]['id'], 'portable-release')
