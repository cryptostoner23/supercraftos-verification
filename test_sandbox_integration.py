"""Opt-in real Docker checks: SUPERCRAFTOS_TEST_DOCKER=1 python -m unittest ..."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from agent_tools import DockerSandbox, Workspace


@unittest.skipUnless(os.getenv('SUPERCRAFTOS_TEST_DOCKER') == '1', 'Requires pre-pulled Docker sandbox image')
class SandboxIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace('test', self.tmp.name)
        self.sandbox = DockerSandbox(timeout=8)
    async def test_real_execution_and_isolation(self):
        self.workspace.write('check.py', 'import os,socket\nassert os.getenv("SUPERCRAFTOS_TEST_SECRET") is None\ntry:\n socket.create_connection(("1.1.1.1",443),.2)\nexcept OSError: pass\nelse: raise AssertionError("network available")\nopen("result.txt","w").write("verified")\nprint("isolation checked")\n')
        with patch.dict(os.environ, {'SUPERCRAFTOS_TEST_SECRET':'never-forward-this'}):
            result = await self.sandbox.run(self.workspace,'python check.py')
        self.assertEqual(result['exit_code'],0,result)
        self.assertEqual(self.workspace.read('result.txt')['content'],'verified')
    async def test_failure_and_timeout_are_not_success(self):
        result = await self.sandbox.run(self.workspace,'python -c "raise ValueError(123)"')
        self.assertNotEqual(result['exit_code'],0)
        sandbox = DockerSandbox(timeout=1)
        result = await sandbox.run(self.workspace,'sleep 30')
        self.assertEqual(result['exit_code'],124);self.assertTrue(result['timed_out'])
    async def test_cancel_removes_container_before_returning(self):
        name='supercraft-job-'+uuid.uuid4().hex
        task=asyncio.create_task(self.sandbox.run(self.workspace,'sleep 30',name=name))
        await asyncio.sleep(1);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        result=subprocess.run(['docker','inspect',name],capture_output=True)
        self.assertNotEqual(result.returncode,0)
    async def test_worker_crash_reconciles_previous_container(self):
        name='supercraft-job-'+uuid.uuid4().hex
        code=('import asyncio;from agent_tools import DockerSandbox,Workspace;'
              f'asyncio.run(DockerSandbox(timeout=10).run(Workspace("test",{self.tmp.name!r}),'
              f'"while true; do echo tick >> progress.txt; sleep 0.2; done",name={name!r}))')
        process=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                if (self.workspace.root/'progress.txt').exists():break
                await asyncio.sleep(.1)
            self.assertTrue((self.workspace.root/'progress.txt').exists())
            process.kill();process.wait(timeout=5)
            # Exactly what a recovering worker does BEFORE inspecting/reusing the workspace.
            await self.sandbox.cleanup(name)
            before=(self.workspace.root/'progress.txt').read_bytes()
            await asyncio.sleep(.5)
            self.assertEqual((self.workspace.root/'progress.txt').read_bytes(),before)
            self.assertNotEqual(subprocess.run(['docker','inspect',name],capture_output=True).returncode,0)
        finally:
            if process.poll() is None:process.kill();process.wait()
            await self.sandbox.cleanup(name)
