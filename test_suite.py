import json, tempfile, unittest
from dynamic_mcp_server import DynamicMCPServer
from langgraph_orchestrator import context_compactor, Graph, HumanApprovalGate
class Tests(unittest.TestCase):
    def test_mcp_registration_and_list_changed(self):
        with tempfile.TemporaryDirectory() as d:
            s=DynamicMCPServer(d+"/tools.json"); s.register_new_tool("echo","Echo",{"type":"object"}); names={tool["name"] for tool in s.dispatch({"method":"tools/list","id":1})["result"]["tools"]}; self.assertIn("echo", names); self.assertIn("execute_python_sandbox", names)
    def test_compaction(self):
        state={"query":"goal","execution_history":[{"x":"y"}]*100}; self.assertIn("context-summary",context_compactor(state,1)["summary"])
    def test_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            result=Graph(d+"/c.json").run({"query":"x"}); self.assertTrue(result["checkpoint_id"])
            with open(d+"/c.json") as source:
                self.assertTrue(json.load(source))
    def test_replacing_a_checkpoint_needs_approval(self):
        # The configuration declares that a destructive write needs a human to
        # approve it, and overwriting a checkpoint destroys the earlier state.
        with tempfile.TemporaryDirectory() as d:
            gate=HumanApprovalGate(approved=False)
            graph=Graph(d+"/c.json", gate=gate, require_approval=True)
            graph.run({"query":"first"})
            with self.assertRaises(PermissionError):
                graph.run({"query":"second"})
            gate.approved=True
            graph.run({"query":"second"})
if __name__=="__main__": unittest.main()
