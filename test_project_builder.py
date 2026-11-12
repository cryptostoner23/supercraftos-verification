import tempfile
import unittest
from agent_tools import Workspace
from project_builder import parse_files
class BuilderTests(unittest.TestCase):
    def test_raw_code_keeps_newlines_and_string_escapes_distinct(self):
        files=parse_files('<file path="app.py">\nvalue = "CSV\\nvalue"\nprint(value)\n</file>\n')
        self.assertEqual(files[0]['content'],'value = "CSV\\nvalue"\nprint(value)\n')
        with tempfile.TemporaryDirectory() as root:
            workspace=Workspace('task',root);workspace.write_many(files)
            self.assertEqual(workspace.read('app.py')['content'],files[0]['content'])
    def test_malformed_partial_and_escaping_payloads_are_rejected(self):
        for value in ['{}','<file path="app.py">\n# comment\\nprint(1)\n</file>\n',
                      '<file path="../secret">\nno\n</file>\n',
                      '<file path="app.py">\nprint(\n</file>\n',
                      '<file path="app.py">\nprint(1)\n</file>\ntrailing text']:
            with self.subTest(value=value),self.assertRaises(ValueError):parse_files(value)
    def test_duplicate_paths_are_rejected(self):
        block='<file path="app.py">\nprint(1)\n</file>\n'
        with self.assertRaises(ValueError):parse_files(block*2)

class BuilderFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_builder_runs_tests_and_acceptance_without_more_planning(self):
        import json
        from pathlib import Path
        from agent_runtime import AgentWorker
        from job_store import JobStore
        class Model:
            calls=[]
            async def complete(self,task,messages):
                self.calls.append(task)
                if task=='agent execution':return json.dumps({'action':'implement_project','arguments':{'reason':'Build requested calculator'}})
                if task=='project implementation':
                    return '<file path="app.py">\ndef add(a,b):\n    return a+b\n</file>\n<file path="test_app.py">\nimport unittest\nfrom app import add\nclass Tests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1,2),3)\n</file>\n<file path="README.md">\nRun python -m unittest discover -v.\n</file>\n'
                if task=='acceptance review':
                    context=json.loads(messages[-1]['content'])
                    assert context['checks'][-1]['exit_code']==0
                    assert any(f['path']=='app.py' for f in context['source'])
                    return '{"accepted":true,"issues":[]}'
                raise AssertionError(task)
        class Sandbox:
            async def run(self,*args,**kwargs):return {'exit_code':0,'output':'Ran 1 test in 0.1s\nOK','timed_out':False}
        with tempfile.TemporaryDirectory() as root:
            store=JobStore(Path(root)/'jobs.sqlite');job=store.submit('Build a calculator with tests', max_steps=2)
            model=Model();await AgentWorker(store,model,Sandbox(),Path(root)/'files').run_once()
            self.assertEqual(store.get(job['id'])['status'],'completed')
            self.assertEqual(store.get(job['id'])['steps'],2)
            self.assertEqual(model.calls,['agent execution','project implementation','acceptance review'])

class BuilderRepairFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_generated_source_is_repaired_before_any_batch_write(self):
        import json
        from pathlib import Path
        from unittest.mock import patch
        from agent_runtime import AgentWorker
        from job_store import JobStore
        class Model:
            drafts=0
            async def complete(self,task,messages):
                if task=='agent execution':return json.dumps({'action':'implement_project','arguments':{'reason':'Build calculator'}})
                if task=='project implementation':
                    self.drafts+=1
                    if self.drafts==1:return '<file path="app.py">\nprint(\n</file>\n'
                    assert 'app.py:1' in messages[-1]['content']
                    return '<file path="app.py">\ndef add(a,b):\n    return a+b\n</file>\n<file path="test_app.py">\nimport unittest\nfrom app import add\nclass Tests(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1,2),3)\n</file>\n'
                if task=='acceptance review':return '{"accepted":true,"issues":[]}'
                raise AssertionError(task)
        class Sandbox:
            async def run(self,*args,**kwargs):return {'exit_code':0,'output':'Ran 1 test in 0.1s\nOK','timed_out':False}
        with tempfile.TemporaryDirectory() as root:
            store=JobStore(Path(root)/'jobs.sqlite');job=store.submit('Build a calculator')
            model=Model()
            with patch('notion_db_setup.private_json'):
                await AgentWorker(store,model,Sandbox(),Path(root)/'files').run_once()
            saved=store.get(job['id']);self.assertEqual(saved['status'],'completed')
            self.assertEqual(model.drafts,2)
            self.assertNotIn('generation_candidate',saved['checkpoint'])
