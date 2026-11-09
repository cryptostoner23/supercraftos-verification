import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest
import httpx
from agent_runtime import AgentWorker, verification_command, validate_python_sources
from agent_tools import Workspace
from job_store import JobStore, Conflict
from test_autonomous import ScriptedModel, FakeSandbox, PLAN, WRITE, CHECK, FINISH

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_outage_resumes_without_spending_action_budget_or_losing_work(self):
        with tempfile.TemporaryDirectory() as root:
            store=JobStore(Path(root)/'jobs.sqlite');job=store.submit('Build a verified program')
            class RecoveringModel(ScriptedModel):
                failures=0
                async def complete(self, task, messages):
                    if task=='agent execution' and self.failures==0:
                        self.failures+=1
                        raise httpx.ReadTimeout('fixture provider outage')
                    return await super().complete(task,messages)
            worker=AgentWorker(store,RecoveringModel([PLAN,WRITE,CHECK,FINISH]),FakeSandbox(),Path(root)/'files')
            await worker.run_once();saved=store.get(job['id'])
            self.assertEqual(saved['status'],'queued');self.assertEqual(saved['steps'],0)
            with store.connect() as db:db.execute('UPDATE jobs SET run_at=? WHERE id=?',(time.time()-1,job['id']))
            await worker.run_once();saved=store.get(job['id'])
            self.assertEqual(saved['status'],'completed');self.assertEqual(saved['steps'],4)
            self.assertEqual(saved['result']['files'][0]['path'],'app.py')
            self.assertEqual(len(store.lessons()),1)
    async def test_model_outage_recovery_is_bounded(self):
        with tempfile.TemporaryDirectory() as root:
            store=JobStore(Path(root)/'jobs.sqlite');job=store.submit('Build a tool')
            class Unavailable:
                async def complete(self,*args):raise httpx.ReadTimeout('private')
            worker=AgentWorker(store,Unavailable(),FakeSandbox(),Path(root)/'files')
            for _ in range(3):
                await worker.run_once()
                with store.connect() as db:db.execute('UPDATE jobs SET run_at=? WHERE id=?',(time.time()-1,job['id']))
            saved=store.get(job['id']);self.assertEqual(saved['status'],'blocked')
            self.assertEqual(saved['checkpoint']['provider_recoveries'],2)
            self.assertEqual(saved['steps'],0)
    async def test_cancelled_wait_is_not_resurrected_by_stale_worker(self):
        with tempfile.TemporaryDirectory() as root:
            store=JobStore(Path(root)/'jobs.sqlite');job=store.submit('Build a tool');store.claim('old');store.cancel(job['id'])
            with self.assertRaises(Conflict):store.defer(job['id'],'old',{},0,30)
            self.assertEqual(store.get(job['id'])['status'],'cancelled')
    def test_inspection_and_invalid_python_cannot_certify_delivery(self):
        self.assertFalse(verification_command('find . -type f'))
        self.assertFalse(verification_command('cat app.py'))
        self.assertTrue(verification_command('python -m unittest discover -v'))
        with tempfile.TemporaryDirectory() as root:
            workspace=Workspace('task',root);workspace.write('app.py','print(1)\\nprint(2)')
            with self.assertRaisesRegex(ValueError,'invalid syntax'):validate_python_sources(workspace,workspace.manifest())

class AutomaticVerificationTests(unittest.TestCase):
    def test_tests_run_once_per_revision_and_retry_after_edit(self):
        from agent_runtime import automatic_verification
        with tempfile.TemporaryDirectory() as root:
            workspace=Workspace('task',root);state={}
            workspace.write('tests/test_app.py','import unittest\n')
            first=automatic_verification(state,workspace)
            self.assertEqual(first['arguments']['command'],'python -m unittest discover -s tests -v')
            self.assertIsNone(automatic_verification(state,workspace))
            workspace.write('app.py','print(1)\n')
            self.assertIsNotNone(automatic_verification(state,workspace))
    def test_native_only_and_empty_workspaces_do_not_start_shell(self):
        from agent_runtime import automatic_verification
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(automatic_verification({},Workspace('task',root)))
