"""Offline checks for deploy/web3-on-demand.patch on the deployed Web3 service."""
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch
sys.path.insert(0, '/opt/web3-agent')
os.environ['W3A_INTEL_ON_DEMAND'] = '1'
from web3agent import intel
from web3agent.intel import analytics, config, store


class OnDemandTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_never_launches_an_ingestor_or_opens_disk_graph(self):
        with patch.object(intel.Runner, 'start', new_callable=AsyncMock) as start, patch.object(store, 'duck') as duck:
            await intel.startup()
            start.assert_not_called(); duck.assert_not_called()
        status = await intel.status()
        self.assertEqual(status['mode'], 'on_demand')
        self.assertFalse(status['running'])
        self.assertFalse(status['persistent_blockchain_cache'])

    async def test_history_requires_an_upstream_adapter_instead_of_false_empty_data(self):
        for response in [await analytics.new_pools(), await analytics.smart_money(),
                         await analytics.alerts(), await analytics.trace_flow('0x' + '1' * 40)]:
            self.assertEqual(response['status'], 'unavailable')
            self.assertFalse(response['persistent_blockchain_cache'])

    async def test_graph_uses_memory(self):
        database = store.duck()
        self.assertEqual(database.execute('SELECT current_database()').fetchone()[0], 'memory')
        self.assertTrue(config.ON_DEMAND)

    async def test_request_time_rpc_uses_transport_without_persisting_a_response(self):
        response = type('Response', (), {'json': lambda self: [{'id': 0, 'result': '0x1'}]})()
        client = AsyncMock()
        client.post.return_value = response
        client.__aenter__.return_value = client
        with patch.object(analytics.httpx, 'AsyncClient', return_value=client):
            result = await analytics._rpc('eth', [('eth_blockNumber', [])])
        self.assertEqual(result, ['0x1'])
        client.post.assert_awaited_once()


if __name__ == '__main__': unittest.main()
