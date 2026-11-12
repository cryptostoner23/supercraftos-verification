"""Public Bitrise API behavior through a local HTTP transport fixture."""
import json
import tempfile
import unittest
from pathlib import Path

import httpx

from bitrise_monitor import BitriseMonitor


class BitriseMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_transition_notifies_once_and_persists(self):
        status = {"value": "in-progress"}
        seen_requests = []

        def handler(request):
            seen_requests.append(request)
            return httpx.Response(200, json={"data": [{
                "slug": "build-123", "status_text": status["value"],
                "build_number": 7, "triggered_workflow": "ios_verify",
            }]})

        messages = []

        async def notify(message):
            messages.append(message)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with tempfile.TemporaryDirectory() as directory:
                monitor = BitriseMonitor("secret", "app-123", notify, Path(directory) / "states.json", client)
                self.assertEqual(await monitor.poll_once(), 1)
                self.assertEqual(await monitor.poll_once(), 0)
                status["value"] = "success"
                self.assertEqual(await monitor.poll_once(), 1)
                self.assertEqual(json.loads(monitor.state_path.read_text()), {"build-123": "success"})
        self.assertEqual(len(messages), 2)
        self.assertIn("success", messages[-1])
        self.assertTrue(all(request.headers["Authorization"] == "secret" for request in seen_requests))

    async def test_invalid_response_does_not_notify(self):
        async def notify(_):
            self.fail("unexpected notification")

        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"data": {}}))) as client:
            with tempfile.TemporaryDirectory() as directory:
                monitor = BitriseMonitor("secret", "app-123", notify, Path(directory) / "states.json", client)
                with self.assertRaises(ValueError):
                    await monitor.poll_once()


if __name__ == "__main__":
    unittest.main()
