import unittest

from agent_trace import task_trace


class TaskTraceTests(unittest.TestCase):
    def test_timeline_exposes_actions_without_command_or_observation_payload(self):
        job = {'id': 'job-1', 'status': 'completed', 'steps': 2,
               'max_steps': 8, 'updated': 10.0,
               'result': {'summary': 'Created the requested file'}, 'error': None}
        events = [
            {'id': 1, 'at': 1.0, 'kind': 'queued', 'detail': {}},
            {'id': 2, 'at': 2.0, 'kind': 'action',
             'detail': {'action': 'run_command', 'step': 2,
                        'note': 'sk-THIS_MUST_NOT_LEAK_123456', 'command': 'secret'}},
            {'id': 3, 'at': 3.0, 'kind': 'observation',
             'detail': {'action': 'run_command', 'result': 'secret output'}},
        ]
        trace = task_trace(job, events)
        self.assertEqual(trace['next_cursor'], 3)
        self.assertEqual(trace['timeline'][1]['action'], 'run_command')
        self.assertEqual(trace['timeline'][1]['step'], 2)
        self.assertNotIn('secret', str(trace).lower())
        self.assertEqual(trace['summary'], 'Created the requested file')

    def test_results_have_bounded_meaningful_status_without_raw_output(self):
        job = {'id': 'j', 'status': 'running', 'steps': 1, 'max_steps': 8,
               'updated': 10, 'result': {}, 'error': None}
        events = [{'id': i, 'at': 1, 'kind': 'observation',
                   'detail': {'action': 'run_command', 'result': '{"exit_code":1,"output":"private output"}'}}
                  for i in range(1, 602)]
        trace = task_trace(job, events)
        self.assertEqual(len(trace['timeline']), 500)
        self.assertEqual(trace['next_cursor'], 500)
        self.assertEqual(trace['timeline'][0]['outcome'], 'error')
        self.assertEqual(trace['timeline'][0]['message'], 'Check exited with code 1.')
        self.assertNotIn('private output', str(trace))
        trace = task_trace(job, [{'id': 9, 'at': 1, 'kind': 'unknown', 'detail': {}}])
        self.assertEqual(trace['next_cursor'], 9)
        self.assertEqual(trace['timeline'], [])

    def test_unknown_events_and_actions_cannot_leak_untrusted_detail(self):
        job = {'id': 'job-2', 'status': 'running', 'steps': 0,
               'max_steps': 8, 'updated': 10.0, 'result': {}, 'error': None}
        events = [{'id': 1, 'at': 1.0, 'kind': 'unsafe', 'detail': {'text': 'secret'}},
                  {'id': 2, 'at': 2.0, 'kind': 'action',
                   'detail': {'action': 'secret', 'step': 'secret'}}]
        trace = task_trace(job, events)
        self.assertEqual(len(trace['timeline']), 1)
        self.assertNotIn('action', trace['timeline'][0])
        self.assertNotIn('step', trace['timeline'][0])


if __name__ == '__main__':
    unittest.main()
