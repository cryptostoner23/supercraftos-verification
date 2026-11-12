"""Offline behavioral tests for leases, replay, isolation and completion evidence."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from agent_runtime import AgentWorker, parse_action
from agent_tools import Workspace, ToolUnavailable
from job_store import JobStore, Conflict


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = JobStore(Path(self.tmp.name)/'queue.sqlite')

    def test_submission_is_idempotent_and_conflicts_are_explicit(self):
        first = self.store.submit('Build a calculator', idempotency_key='request-1')
        second = self.store.submit('Build a calculator', idempotency_key='request-1')
        self.assertEqual(first['id'], second['id'])
        with self.assertRaises(Conflict):
            self.store.submit('Build something else', idempotency_key='request-1')
        self.assertEqual(len(self.store.list()), 1)

    def test_only_one_worker_claims_each_task(self):
        self.store.submit('Build one task')
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda n: self.store.claim(str(n)), range(8)))
        self.assertEqual(sum(job is not None for job in jobs), 1)

    def test_native_requirements_are_atomic_and_part_of_request_identity(self):
        state = {'required_native': [{'name': 'register_developer_account', 'provider': 'steel'}]}
        job = self.store.submit('Verify account', idempotency_key='account', initial_state=state)
        self.assertEqual(self.store.claim('worker')['checkpoint'], state)
        self.assertEqual(self.store.submit('Verify account', idempotency_key='account', initial_state=state)['id'], job['id'])
        with self.assertRaises(Conflict):
            self.store.submit('Verify account', idempotency_key='account')

    def test_restart_recovers_expired_lease_and_rejects_stale_worker(self):
        job = self.store.submit('Build a task')
        self.store.claim('old', lease_seconds=-1)
        recovered = JobStore(self.store.path).claim('new')
        self.assertEqual(recovered['id'], job['id'])
        self.assertFalse(self.store.finish(job['id'], 'old', 'completed'))
        self.assertTrue(self.store.finish(job['id'], 'new', 'completed'))
        self.assertEqual(self.store.events(job['id'])[2]['kind'], 'recovered')

    def test_scheduled_and_cancelled_jobs_do_not_run(self):
        job = self.store.submit('Later task', run_at=time.time()+3600)
        self.assertIsNone(self.store.claim('one'))
        self.store.cancel(job['id'])
        self.assertIsNone(self.store.claim('two'))
        self.assertEqual(self.store.get(job['id'])['status'], 'cancelled')

    def test_cancellation_wins_over_late_completion(self):
        job = self.store.submit('Cancel this task')
        self.store.claim('worker')
        self.store.cancel(job['id'])
        self.assertFalse(self.store.finish(job['id'], 'worker', 'completed'))
        self.assertEqual(self.store.get(job['id'])['status'], 'cancelled')

    def test_retry_preserves_observations_and_rejects_running_job(self):
        job = self.store.submit('Retry this task')
        self.store.claim('worker')
        with self.assertRaises(Conflict): self.store.retry(job['id'])
        self.store.checkpoint(job['id'], 'worker', {'history': ['observed']}, 2)
        self.store.finish(job['id'], 'worker', 'failed')
        result = self.store.retry(job['id'])
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(result['checkpoint']['history'], ['observed'])

    def test_unverified_jobs_cannot_create_lessons(self):
        job = self.store.submit('Unverified result')
        with self.assertRaises(ValueError): self.store.remember(job['id'], 'A lesson')

    def test_limits_reject_nonfinite_schedule_and_boolean_steps(self):
        for value in (float('nan'), float('inf'), True, 'tomorrow'):
            with self.assertRaises(ValueError): self.store.submit('Build task', run_at=value)
        with self.assertRaises(ValueError): self.store.submit('Build task', max_steps=True)


class FileTests(unittest.TestCase):
    def test_traversal_symlinks_and_file_limits(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Workspace('task', root)
            workspace.write('src/app.py', 'print(1)')
            self.assertEqual(workspace.read('src/app.py')['content'], 'print(1)')
            for name in ('../secret', '/etc/passwd', 'src/../../outside', ''):
                with self.assertRaises(ValueError): workspace.write(name, 'no')
            (workspace.root/'escape').symlink_to(Path(root), target_is_directory=True)
            with self.assertRaises(ValueError): workspace.read('escape/secret')
            with self.assertRaises(ValueError): workspace.write('huge', 'x'*256001)
            before = workspace.manifest()
            workspace.write('src/app.py', 'print(2)')
            self.assertNotEqual(before, workspace.manifest())


class ScriptedModel:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.contexts = []
    async def complete(self, task, messages):
        self.contexts.append(messages)
        if task == 'acceptance review':
            return json.dumps({'accepted': True, 'issues': []})
        result = next(self.actions)
        return result if isinstance(result, str) else json.dumps(result)


def action(name, **args):
    return {'action': name, 'arguments': args}


PLAN = action('plan', steps=['Implement', 'Test'], acceptance=['Check edge cases'])
WRITE = action('write_file', path='app.py', content='assert 1 + 1 == 2\n')
CHECK = action('run_command', command='python app.py')
FINISH = action('finish', summary='Created app.py and checked it', lesson='Run checks after edits')


class FakeSandbox:
    def __init__(self, codes=(0,)):
        self.codes = iter(codes)
    async def run(self, workspace, command, **kwargs):
        return {'exit_code': next(self.codes), 'output': 'fixture check result', 'timed_out': False}


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = JobStore(Path(self.tmp.name)/'jobs.sqlite')
        self.root = Path(self.tmp.name)/'workspaces'

    async def run_actions(self, actions, sandbox=None, max_steps=24):
        job = self.store.submit('Build a verified program', max_steps=max_steps)
        self.worker = AgentWorker(self.store, ScriptedModel(actions), sandbox or FakeSandbox(), self.root)
        await self.worker.run_once()
        return self.store.get(job['id'])

    async def test_model_outage_preserves_checkpoint_for_explicit_resume(self):
        import httpx
        class UnavailableModel:
            async def complete(self, task, messages):
                raise httpx.ReadTimeout('private provider details must stay private')
        job = self.store.submit('Build a tool')
        await AgentWorker(self.store, UnavailableModel(), FakeSandbox(), self.root).run_once()
        saved = self.store.get(job['id'])
        self.assertEqual(saved['status'], 'queued')
        self.assertIsNone(saved['error'])
        self.assertEqual(saved['checkpoint']['provider_recoveries'], 1)
        self.assertGreater(saved['run_at'], saved['updated'])
        self.assertEqual(saved['steps'], 0)
        self.assertEqual(saved['checkpoint']['history'], [])

    async def test_repeated_planning_is_bounded_without_fabricated_progress(self):
        job = await self.run_actions([PLAN] * 4, max_steps=12)
        self.assertEqual(job['status'], 'blocked')
        self.assertEqual(job['steps'], 4)
        self.assertIn('without executing', job['error'])
        self.assertEqual(job['checkpoint']['plan'], ['Implement', 'Test'])
        self.assertEqual(job['checkpoint']['checks'], [])

    async def test_agent_can_recover_from_redundant_plan_and_deliver(self):
        job = await self.run_actions([PLAN, PLAN, WRITE, CHECK, FINISH])
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['result']['files'][0]['path'], 'app.py')
        self.assertTrue(any('Stop planning' in json.dumps(event) for event in self.store.events(job['id'])))

    async def test_end_to_end_persists_files_checks_and_lessons(self):
        job = await self.run_actions([PLAN, WRITE, CHECK, FINISH])
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['result']['checks'][0]['exit_code'], 0)
        self.assertEqual(job['result']['files'][0]['path'], 'app.py')
        self.assertEqual(len(self.store.lessons()), 1)

    async def test_installed_tools_are_discovered_in_context_and_executed(self):
        class CatalogModel(ScriptedModel):
            async def complete(inner, task, messages):
                if task == 'agent execution':
                    context = json.loads(messages[-1]['content'])
                    names = {tool['name'] for tool in context['native_tools']}
                    self.assertIn('screen_product_design', names)
                    self.assertIn('run_quest_actions', names)
                    self.assertIn('submit_grant_application', names)
                    self.assertNotIn('submit_autonomous_task', names)
                return await super(CatalogModel, inner).complete(task, messages)
        job = self.store.submit('Screen a physical product and deliver checks')
        model = CatalogModel([PLAN, {'action': 'native_tool', 'arguments': {'name': 'screen_product_design', 'arguments': {}}}, WRITE, CHECK, FINISH])
        await AgentWorker(self.store, model, FakeSandbox(), self.root).run_once()
        result = self.store.get(job['id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['checkpoint']['native_evidence'][0]['name'], 'screen_product_design')
        self.assertIn('readiness', result['checkpoint']['native_evidence'][0]['result'])

    async def test_native_only_task_finishes_from_real_tool_evidence(self):
        job = await self.run_actions([
            {'action': 'native_tool', 'arguments': {'name': 'screen_product_design', 'arguments': {}}},
            action('finish', summary='Screened the actual enclosure design; manufacturing checks remain open.', lesson='Record native tool results and their limits'),
        ], max_steps=2)
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['result']['files'], [])
        self.assertEqual(job['result']['checks'], [])
        self.assertEqual(job['result']['native_evidence'][0]['name'], 'screen_product_design')
        self.assertEqual(job['result']['native_evidence'][0]['result']['readiness'], 'prototype_candidate')

    async def test_reviewer_rejection_requires_repair_before_delivery(self):
        class Reviewer(ScriptedModel):
            reviews = 0
            async def complete(self, task, messages):
                if task == 'acceptance review':
                    self.reviews += 1
                    return json.dumps({'accepted': self.reviews > 1, 'issues': ['Missing negative input check'] if self.reviews == 1 else []})
                return await super().complete(task, messages)
        job = self.store.submit('Build a program with negative input checks')
        model = Reviewer([PLAN, WRITE, CHECK, FINISH,
            action('write_file', path='app.py', content='assert abs(-2) == 2\n'), CHECK, FINISH])
        await AgentWorker(self.store, model, FakeSandbox((0, 0)), self.root).run_once()
        result = self.store.get(job['id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(model.reviews, 2)
        self.assertEqual(len(result['result']['checks']), 2)
        self.assertTrue(any('Missing negative input' in json.dumps(e) for e in self.store.events(job['id'])))

    async def test_retry_waits_for_previous_workspace_cleanup(self):
        entered, cleaning, allow_cleanup, recovered = (asyncio.Event() for _ in range(4))
        class SlowCleanup:
            async def run(self, *args, **kwargs):
                entered.set()
                try:
                    await asyncio.sleep(30)
                finally:
                    cleaning.set()
                    await allow_cleanup.wait()
            async def cleanup(self, name):
                recovered.set()
        sandbox = SlowCleanup()
        job = self.store.submit('Cancel and retry during slow cleanup')
        old = AgentWorker(self.store, ScriptedModel([PLAN, WRITE, CHECK]), sandbox, self.root)
        old_task = asyncio.create_task(old.run_once())
        await asyncio.wait_for(entered.wait(), 3)
        self.store.cancel(job['id']); self.store.retry(job['id'])
        new = AgentWorker(self.store, ScriptedModel([action('blocked', reason='Recovered safely')]), sandbox, self.root)
        new_task = asyncio.create_task(new.run_once())
        try:
            await asyncio.wait_for(cleaning.wait(), 3)
            await asyncio.sleep(1.2)
            self.assertFalse(old_task.done())
            self.assertFalse(recovered.is_set())
            self.assertFalse(new_task.done())
        finally:
            allow_cleanup.set()
            await asyncio.wait_for(asyncio.gather(old_task, new_task), 4)
        self.assertTrue(recovered.is_set())
        self.assertEqual(self.store.get(job['id'])['error'], 'Recovered safely')

    async def test_cannot_finish_without_actual_checks(self):
        job = await self.run_actions([PLAN, WRITE, FINISH], max_steps=3)
        self.assertEqual(job['status'], 'blocked')
        self.assertFalse(self.store.lessons())

    async def test_edits_invalidate_prior_verification(self):
        job = await self.run_actions([PLAN, WRITE, CHECK, action('write_file', path='app.py', content='broken'), FINISH], max_steps=5)
        self.assertEqual(job['status'], 'blocked')

    async def test_failed_check_is_repaired_and_rechecked(self):
        job = await self.run_actions([PLAN, WRITE, CHECK, WRITE, CHECK, FINISH], FakeSandbox((1, 0)))
        self.assertEqual(job['status'], 'completed')
        self.assertEqual([c['exit_code'] for c in job['result']['checks']], [1, 0])

    async def test_command_exception_invalidates_previous_success(self):
        class Errors:
            calls = 0
            async def run(self, *args, **kwargs):
                self.calls += 1
                if self.calls == 2: raise ValueError('command output limit exceeded')
                return {'exit_code': 0, 'output': 'ok', 'timed_out': False}
        job = await self.run_actions([PLAN, WRITE, CHECK, CHECK, FINISH], Errors(), max_steps=5)
        self.assertEqual(job['status'], 'blocked')
        self.assertIsNone(job['checkpoint']['checks'][-1]['exit_code'])

    async def test_zero_byte_only_delivery_cannot_complete(self):
        job = await self.run_actions([PLAN, action('write_file', path='empty', content=''), CHECK, FINISH], max_steps=4)
        self.assertEqual(job['status'], 'blocked')

    async def test_immediate_retry_does_not_stop_worker(self):
        entered = asyncio.Event()
        class Waiting:
            async def complete(self, *args):
                entered.set()
                await asyncio.sleep(30)
        job = self.store.submit('Retry while model is running')
        worker = AgentWorker(self.store, Waiting(), FakeSandbox(), self.root)
        task = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(entered.wait(), 3)
        self.store.cancel(job['id']); self.store.retry(job['id'])
        self.assertTrue(await asyncio.wait_for(task, 4))
        self.assertEqual(self.store.get(job['id'])['status'], 'queued')

    async def test_malformed_model_response_recovers_within_budget(self):
        job = await self.run_actions(['not JSON', PLAN, WRITE, CHECK, FINISH])
        self.assertEqual(job['status'], 'completed')
        self.assertTrue(any(e['kind']=='invalid_model_action' for e in self.store.events(job['id'])))

    async def test_flat_provider_requests_execute_without_protocol_loop(self):
        flat = [{'action': value['action'], **value['arguments']} for value in [PLAN, WRITE, CHECK, FINISH]]
        job = await self.run_actions(flat)
        self.assertEqual(job['status'], 'completed')
        self.assertFalse(any(e['kind']=='invalid_model_action' for e in self.store.events(job['id'])))

    async def test_repeated_invalid_requests_stop_without_burning_remaining_budget(self):
        job = await self.run_actions(['{}'] * 4, max_steps=24)
        self.assertEqual(job['status'], 'blocked')
        self.assertEqual(job['steps'], 4)
        self.assertIn('four consecutive', job['error'])

    async def test_local_artifacts_cannot_fake_account_verification(self):
        job = self.store.submit('Verify account', max_steps=4,
            initial_state={'required_native': [{'name': 'register_developer_account', 'provider': 'steel'}]})
        model = ScriptedModel([PLAN, WRITE, CHECK, FINISH])
        await AgentWorker(self.store, model, FakeSandbox(), self.root).run_once()
        result = self.store.get(job['id'])
        self.assertEqual(result['status'], 'blocked')
        self.assertIn('no verified provider receipt', str(result['checkpoint']))

    def test_ambiguous_or_unknown_action_fields_are_rejected(self):
        for value in ['{"action":"read_file","arguments":{"path":"safe"},"path":"other"}',
                      '{"action":"read_file","path":"one","path":"two"}',
                      '{"action":"run_command","command":"true","extra":"ignored"}',
                      '{"action":"unknown","arguments":{}}']:
            with self.assertRaises(ValueError): parse_action(value)

    async def test_unavailable_sandbox_reports_blocker_without_host_execution(self):
        class Unavailable:
            async def run(self, *args, **kwargs): raise ToolUnavailable('Docker unavailable')
        job = await self.run_actions([PLAN, WRITE, CHECK], Unavailable())
        self.assertEqual(job['status'], 'blocked')
        self.assertEqual(job['error'], 'Docker unavailable')

    async def test_restart_does_not_blindly_replay_interrupted_command(self):
        job = self.store.submit('Recover work')
        self.store.claim('crashed', lease_seconds=-1)
        self.store.checkpoint(job['id'], 'crashed', {'pending': 'run_command'}, 2)
        worker = AgentWorker(self.store, ScriptedModel([action('blocked', reason='Need inspection')]), FakeSandbox(), self.root)
        await worker.run_once()
        context = json.loads(worker.optimizer.contexts[0][1]['content'])
        self.assertIn('interrupted', context['history'][0]['result'])

    async def test_cancellation_interrupts_running_tool(self):
        entered = asyncio.Event(); stopped = asyncio.Event()
        class Hanging:
            async def run(self, *args, **kwargs):
                entered.set()
                try: await asyncio.sleep(30)
                finally: stopped.set()
        job = self.store.submit('Cancel running tool')
        worker = AgentWorker(self.store, ScriptedModel([PLAN, WRITE, CHECK]), Hanging(), self.root)
        task = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(entered.wait(), 3)
        self.store.cancel(job['id'])
        await asyncio.wait_for(task, 4)
        self.assertTrue(stopped.is_set())
        self.assertEqual(self.store.get(job['id'])['status'], 'cancelled')


if __name__ == '__main__': unittest.main()
