import tempfile
import unittest
from agent_runtime import task_relative_path
from agent_tools import Workspace

class BatchWorkspaceTests(unittest.TestCase):
    def test_invalid_later_path_does_not_write_first_file(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Workspace('task', root)
            with self.assertRaises(ValueError):
                workspace.write_many([{'path': 'safe.py', 'content': 'ok'}, {'path': '../secret', 'content': 'no'}])
            self.assertEqual(workspace.manifest(), [])
            result = workspace.write_many([{'path': 'src/app.py', 'content': 'print(1)'}, {'path': 'README.md', 'content': 'Run src/app.py'}])
            self.assertEqual(len(result['files']), 2)
            self.assertEqual(workspace.read('src/app.py')['content'], 'print(1)')
    def test_virtual_alias_does_not_allow_host_paths_or_traversal(self):
        self.assertEqual(task_relative_path('/task/src/app.py'), 'src/app.py')
        self.assertEqual(task_relative_path('/workspace/src/app.py'), 'src/app.py')
        with tempfile.TemporaryDirectory() as root:
            workspace = Workspace('task', root)
            for path in ['/etc/passwd', '/task/../../etc/passwd', '/workspace/../secret']:
                with self.assertRaises(ValueError):
                    workspace.write(task_relative_path(path), 'no')
