"""Task tool transport uses the same durable queue as the dashboard and worker."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dynamic_mcp_server import DynamicMCPServer
from job_store import JobStore


class TaskMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_inspect_cancel_and_validation(self):
        with tempfile.TemporaryDirectory() as root:
            store = JobStore(Path(root) / 'jobs.sqlite')
            server = DynamicMCPServer(Path(root) / 'tools.json')
            async def call(name, arguments):
                return await server.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': name, 'arguments': arguments}})
            with patch('job_store.JobStore', return_value=store):
                bad = await call('submit_autonomous_task', {'query': 'bad', 'max_steps': 1000})
                self.assertIn('error', bad)
                self.assertEqual(store.list(), [])
                response = await call('submit_autonomous_task', {'query': 'Build a CSV utility', 'idempotency_key': 'mcp-request'})
                job = json.loads(response['result']['content'][0]['text'])
                self.assertEqual(job['status'], 'queued')
                self.assertNotIn('checkpoint', job)
                duplicate = await call('submit_autonomous_task', {'query': 'Build a CSV utility', 'idempotency_key': 'mcp-request'})
                self.assertEqual(json.loads(duplicate['result']['content'][0]['text'])['id'], job['id'])
                found = await call('inspect_autonomous_task', {'job_id': job['id']})
                self.assertEqual(json.loads(found['result']['content'][0]['text'])['events'][0]['kind'], 'queued')
                cancelled = await call('cancel_autonomous_task', {'job_id': job['id']})
                self.assertEqual(json.loads(cancelled['result']['content'][0]['text'])['status'], 'cancelled')
            self.assertEqual(JobStore(store.path).get(job['id'])['status'], 'cancelled')
