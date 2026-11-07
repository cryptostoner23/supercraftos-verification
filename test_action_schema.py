"""Regression cases captured from live agent actions that exhausted task budgets."""
import unittest
from jsonschema import Draft202012Validator
from token_optimizer import ACTION_SCHEMA


class ActionSchemaTests(unittest.TestCase):
    def test_incomplete_live_actions_cannot_pass_generation_contract(self):
        validator = Draft202012Validator(ACTION_SCHEMA)
        for action in [
            {'action': 'plan', 'arguments': {'steps': ['Implement CLI']}},
            {'action': 'native_tool', 'arguments': {'provider': 'steel'}},
            {'action': 'blocked', 'arguments': {}},
            {'action': 'write_file', 'arguments': {'path': 'main.py'}},
        ]:
            with self.subTest(action=action):
                self.assertFalse(validator.is_valid(action))

    def test_executable_actions_retain_their_actual_arguments(self):
        validator = Draft202012Validator(ACTION_SCHEMA)
        for action in [
            {'action': 'plan', 'arguments': {'steps': ['Implement CLI'], 'acceptance': ['Tests pass']}},
            {'action': 'native_tool', 'arguments': {'name': 'register_developer_account', 'arguments': {'provider': 'steel'}}},
            {'action': 'blocked', 'arguments': {'reason': 'Provider rejected authentication'}},
            {'action': 'write_file', 'arguments': {'path': 'main.py', 'content': 'print(1)\n'}},
            {'action': 'run_command', 'arguments': {'command': 'python -m unittest -v'}},
        ]:
            with self.subTest(action=action):
                validator.validate(action)

    def test_stalled_read_cannot_consume_the_entire_remaining_budget(self):
        from token_optimizer import execution_schema
        import json
        observation = {'action': 'read_file', 'arguments': {'path': 'main.py'}, 'result': '{"content":"print(1)"}'}
        schema = execution_schema([{'role': 'user', 'content': json.dumps({'history': [observation, observation]})}])
        validator = Draft202012Validator(schema)
        self.assertFalse(validator.is_valid({'action': 'read_file', 'arguments': {'path': 'main.py'}}))
        self.assertTrue(validator.is_valid({'action': 'run_command', 'arguments': {'command': 'python main.py'}}))
        changed = dict(observation, result='{"content":"print(2)"}')
        self.assertIs(execution_schema([{'content': json.dumps({'history': [observation, changed]})}]), ACTION_SCHEMA)

    def test_empty_workspace_cannot_repeat_discovery_or_replan(self):
        from token_optimizer import execution_schema
        import json
        schema=execution_schema([{'content':json.dumps({'files':[],'plan':['Use installed grant tools']})}])
        validator=Draft202012Validator(schema)
        for name,args in [('list_files',{}),('read_file',{'path':'README.md'}),('plan',{'steps':['Repeat'],'acceptance':['Repeat']})]:
            self.assertFalse(validator.is_valid({'action':name,'arguments':args}))
        self.assertTrue(validator.is_valid({'action':'native_tool','arguments':{'name':'list_blockchain_grants','arguments':{}}}))
