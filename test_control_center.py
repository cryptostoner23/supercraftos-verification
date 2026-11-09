import http.client
import json
import threading
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import supercraftos_cli as app


class ControlCenterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = app.BoundedHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps(body).encode() if body is not None else None
        supplied = {"Content-Type": "application/json", **(headers or {})}
        connection.request(method, path, payload, supplied)
        response = connection.getresponse(); data = response.read(); connection.close()
        return response.status, response.getheader("Content-Type"), data

    def test_dashboard_embeds_private_token_and_status_does_not_expose_it(self):
        status, content_type, body = self.request("GET", "/")
        self.assertEqual(status, 200); self.assertIn("text/html", content_type)
        self.assertIn(app.STATE.token.encode(), body)
        status, _, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200); self.assertNotIn(app.STATE.token.encode(), body)
        self.assertNotIn("csrf", json.loads(body))

    def test_mutations_require_token(self):
        status, _, body = self.request("POST", "/api/runtime/start", {})
        self.assertEqual(status, 403); self.assertEqual(json.loads(body)["error"], "unauthorized")

    def test_invalid_workflow_is_rejected_before_model_call(self):
        with patch.object(app, "run_workflow") as run:
            status, _, body = self.request("POST", "/api/workflows", {"query": "x"}, {
                "X-SuperCraftOS-Token": app.STATE.token,
                "Origin": f"http://127.0.0.1:{self.port}",
            })
        self.assertEqual(status, 400); self.assertEqual(json.loads(body)["error"], "query_length"); run.assert_not_called()

    def test_firecrawl_registration_is_visible(self):
        with patch.object(app, 'read_json', side_effect=[{'firecrawl': {'status': 'blocked'}}, {}]):
            rows = app.registration_rows()
        self.assertTrue(any(row["name"].lower() == "firecrawl" for row in rows))

    def test_nonlocal_host_cannot_read_control_session(self):
        status, _, body = self.request("GET", "/", headers={"Host": "untrusted.example"})
        self.assertEqual(status, 403)
        self.assertNotIn(app.STATE.token.encode(), body)

    def test_local_network_host_is_accepted(self):
        # The phone reaches the agent on a LAN without a VPN or a mesh tunnel.
        for host in ["192.168.1.50", "10.0.0.7", "172.16.4.2", "169.254.1.1", "macbook.local"]:
            status, _, body = self.request("GET", "/", headers={"Host": host})
            self.assertEqual(status, 200, host)
        for host in ["127.0.0.1", "localhost", "[::1]"]:
            status, _, _ = self.request("GET", "/", headers={"Host": host})
            self.assertEqual(status, 200, host)

    def test_public_host_is_still_rejected(self):
        status, _, body = self.request("GET", "/", headers={"Host": "untrusted.example"})
        self.assertEqual(status, 403)
        self.assertNotIn(app.STATE.token.encode(), body)
        status, _, _ = self.request("GET", "/", headers={"Host": "8.8.8.8"})
        self.assertEqual(status, 403)

    def test_nonstring_query_is_rejected(self):
        status, _, body = self.request("POST", "/api/workflows", {"query": {"operation": "x"}}, {
            "X-SuperCraftOS-Token": app.STATE.token})
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "query_type")

    def test_cross_origin_mutation_is_rejected(self):
        status, _, _ = self.request("POST", "/api/runtime/start", {}, {
            "X-SuperCraftOS-Token": app.STATE.token, "Origin": "https://untrusted.example"})
        self.assertEqual(status, 403)

    def test_completed_workflow_cannot_be_approved_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflows.json"
            path.write_text(json.dumps([{"thread_id": "completed-test", "status": "completed"}]))
            with patch.object(app, "WORKFLOWS", path):
                status, _, body = self.request("POST", "/api/workflows/completed-test/approve", {}, {
                    "X-SuperCraftOS-Token": app.STATE.token})
        self.assertEqual(status, 409)
        self.assertEqual(json.loads(body)["error"], "workflow_not_pending")

    def test_concurrent_status_requests(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            responses = list(workers.map(lambda _: self.request("GET", "/api/status"), range(40)))
        self.assertTrue(all(status == 200 and json.loads(body)["project"] == "SuperCraftOS" for status, _, body in responses))

    def test_malformed_host_is_rejected_without_crashing(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "["})[0], 403)

    def test_all_read_entrypoints_return_valid_json(self):
        for path in ("status", "tools", "integrations", "registrations", "workflows"):
            status, _, body = self.request("GET", "/api/" + path)
            self.assertEqual(status, 200)
            self.assertIsInstance(json.loads(body), dict)

    def test_native_session_uses_guarded_public_entrypoint(self):
        status, _, body = self.request("GET", "/api/session")
        self.assertEqual(status, 200)
        token = json.loads(body)["token"]
        self.assertEqual(self.request("POST", "/api/workflows", {"query": "x"}, {
            "X-SuperCraftOS-Token": token})[0], 400)
        self.assertEqual(self.request("GET", "/api/session", headers={"Host": "outside.example"})[0], 403)

    def test_corrupt_state_returns_sanitized_error(self):
        with patch.object(app, "integration_rows", side_effect=ValueError("private-state-detail")):
            status, _, body = self.request("GET", "/api/integrations")
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body), {"error": "state_unavailable"})
        self.assertNotIn(b"private-state-detail", body)



class AutonomousAPITests(unittest.TestCase):
    setUpClass = classmethod(ControlCenterTests.setUpClass.__func__)
    tearDownClass = classmethod(ControlCenterTests.tearDownClass.__func__)
    request = ControlCenterTests.request
    def test_account_job_requires_actual_native_receipt_and_is_idempotent(self):
        from job_store import JobStore
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory)/'jobs.sqlite')
            with patch.object(app, 'job_store', return_value=store):
                headers = {'X-SuperCraftOS-Token':app.STATE.token, 'Idempotency-Key':'account-check'}
                status, _, body = self.request('POST', '/api/accounts/register', {'provider':'steel'}, headers)
                self.assertEqual(status,202)
                job=json.loads(body)
                self.assertEqual(store.get(job['id'])['checkpoint']['required_native'],
                    [{'name':'register_developer_account','provider':'steel'}])
                again=json.loads(self.request('POST','/api/accounts/register',{'provider':'steel'},headers)[2])
                self.assertEqual(again['id'],job['id'])
                self.assertEqual(self.request('POST','/api/accounts/register',{'provider':'firecrawl'},headers)[0],409)
                self.assertEqual(self.request('POST','/api/accounts/register',{'provider':'unknown'},headers)[0],400)
                self.assertEqual(self.request('POST','/api/accounts/register',{'provider':'steel','url':'https://invalid.example'},headers)[0],400)
                self.assertEqual(self.request('POST','/api/accounts/register',{'provider':'steel'})[0],403)
    def test_queue_job_without_waiting_for_model(self):
        from job_store import JobStore
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory)/'jobs.sqlite')
            with patch.object(app, 'job_store', return_value=store), patch.object(app, 'run_workflow') as legacy:
                headers={'X-SuperCraftOS-Token':app.STATE.token,'Idempotency-Key':'fixture-idempotency'}
                status,_,body=self.request('POST','/api/jobs',{'query':'Build tested calculator'},headers)
                self.assertEqual(status,202)
                job=json.loads(body);self.assertEqual(job['status'],'queued')
                self.assertNotIn('checkpoint',job)
                again=json.loads(self.request('POST','/api/jobs',{'query':'Build tested calculator'},headers)[2])
                self.assertEqual(again['id'],job['id']);legacy.assert_not_called()
                self.assertEqual(self.request('POST','/api/jobs',{'query':'Different request'},headers)[0],409)
                self.assertEqual(self.request('POST',f"/api/jobs/{job['id']}/cancel",{},headers)[0],200)
                self.assertEqual(store.get(job['id'])['status'],'cancelled')
                self.assertEqual(self.request('GET',f"/api/jobs/{job['id']}/events")[0],200)
                self.assertEqual(self.request('GET',f"/api/jobs/{job['id']}/events?after=invalid")[0],400)
                trace_status, _, trace_body = self.request('GET',f"/api/jobs/{job['id']}/trace")
                self.assertEqual(trace_status, 200)
                trace = json.loads(trace_body)
                self.assertEqual(trace['job_id'], job['id'])
                self.assertEqual([event['kind'] for event in trace['timeline']], ['queued', 'cancelled'])
                self.assertEqual(self.request('GET',f"/api/jobs/{job['id']}/trace?after=invalid")[0],400)
                self.assertEqual(self.request('GET',f"/api/jobs/{job['id']}/trace?after={10**50}")[0],400)
                self.assertEqual(self.request('GET','/api/jobs/')[0],404)
    def test_tool_execution_routes_to_real_mcp_and_validates_schema(self):
        headers = {'X-SuperCraftOS-Token': app.STATE.token}
        # Execute the local deterministic built-in, not a mocked renderer or paid provider.
        status, _, body = self.request('POST', '/api/tools/call', {
            'name': 'screen_product_design', 'arguments': {'name': 'fixture enclosure'}}, headers)
        self.assertEqual(status, 200)
        response = json.loads(body)
        self.assertEqual(response['jsonrpc'], '2.0')
        self.assertEqual(response['id'], 1)
        self.assertNotIn('error', response)
        result = json.loads(response['result']['content'][0]['text'])
        self.assertEqual(result['spec']['name'], 'fixture enclosure')
        self.assertIn(result['readiness'], {'prototype_candidate', 'needs_revision'})
        self.assertNotEqual(response['result'].get('isError'), True)
        for request in ({'name': 'unknown', 'arguments': {}},
                        {'name': 'screen_product_design', 'arguments': {'width_mm': -10}}):
            status, _, body = self.request('POST', '/api/tools/call', request, headers)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)['error']['code'], -32602)
        self.assertEqual(self.request('POST', '/api/tools/call', {'name': 'screen_product_design'})[0], 403)
        for request in ({'name': []}, {'name': 'test', 'arguments': []}, {'name': 'test', 'extra': True}):
            self.assertEqual(self.request('POST', '/api/tools/call', request, headers)[0], 400)

    def test_tool_output_and_transport_failures_have_explicit_errors(self):
        headers = {'X-SuperCraftOS-Token': app.STATE.token}
        with patch.object(app, 'rpc', return_value={'result': 'x' * 2_000_001}):
            self.assertEqual(self.request('POST', '/api/tools/call', {'name': 'test'}, headers)[0], 502)
        with patch.object(app, 'rpc', side_effect=RuntimeError('private diagnostic')):
            status, _, body = self.request('POST', '/api/tools/call', {'name': 'test'}, headers)
            self.assertEqual(status, 503)
            self.assertNotIn(b'private diagnostic', body)

    def test_same_host_different_port_origin_is_rejected(self):
        self.assertEqual(self.request('POST','/api/jobs',{'query':'Build test'},
            {'X-SuperCraftOS-Token':app.STATE.token,'Origin':'http://127.0.0.1:1'})[0],403)



class EvidenceAPITests(unittest.TestCase):
    setUpClass = classmethod(ControlCenterTests.setUpClass.__func__)
    tearDownClass = classmethod(ControlCenterTests.tearDownClass.__func__)
    request = ControlCenterTests.request
    def test_completed_download_is_bound_to_verified_manifest(self):
        from job_store import JobStore
        from agent_tools import Workspace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JobStore(root/'jobs.sqlite')
            job = store.submit('Create a verified file')
            store.claim('worker')
            workspace = Workspace(job['id'], root/'data/workspaces')
            workspace.write('result.txt', 'verified content')
            store.finish(job['id'], 'worker', 'completed', {'files': workspace.manifest()})
            with patch.object(app, 'job_store', return_value=store), patch.object(app, 'ROOT', root):
                path = f"/api/jobs/{job['id']}/files/result.txt"
                self.assertEqual(self.request('GET',path)[2], b'verified content')
                workspace.write('result.txt','tampered content')
                self.assertEqual(self.request('GET',path)[0],409)

    def test_memory_delete_requires_authentication_and_forgets(self):
        from job_store import JobStore
        with tempfile.TemporaryDirectory() as directory:
            store = JobStore(Path(directory)/'jobs.sqlite')
            job=store.submit('Create an example');store.claim('worker')
            store.finish(job['id'],'worker','completed',{'review':{'accepted':True}})
            store.remember(job['id'],'Verify the output before delivery')
            with patch.object(app,'job_store',return_value=store):
                code,_,body=self.request('GET','/api/agent/memory')
                self.assertEqual(code,200)
                ident=json.loads(body)['lessons'][0]['id']
                self.assertEqual(self.request('POST','/api/agent/memory/forget',{'id':ident})[0],403)
                self.assertEqual(self.request('POST','/api/agent/memory/forget',{'id':ident},{'X-SuperCraftOS-Token':app.STATE.token})[0],200)
                self.assertEqual(store.lessons(),[])

if __name__ == "__main__": unittest.main()
