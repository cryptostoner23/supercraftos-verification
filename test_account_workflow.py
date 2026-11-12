import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from account_tools import CHECK_ENDPOINTS
from agent_runtime import AgentWorker
from job_store import JobStore


class NoModel:
    async def complete(self, *args, **kwargs):
        raise AssertionError('Account workflows must not consume model calls')


class AccountWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=JobStore(self.root/'jobs.sqlite3')

    async def execute(self,receipt,provider='steel'):
        job=self.store.submit('Verify existing account',max_steps=6,
            initial_state={'workflow':'developer_account','account_provider':provider})
        with patch('account_workflow.register_developer_account',new=AsyncMock(return_value=receipt)) as operation:
            await AgentWorker(self.store,NoModel(),workspace_root=self.root/'work').run_once()
        operation.assert_awaited_once_with({'provider':provider})
        return self.store.get(job['id'])

    def verified(self):
        return {'provider':'steel','status':'verified_existing','credential_verified':True,
                'credential_present':True,'registration_attempted':False,'attempt_id':None,
                'checked_at':1700000000,'reason':'Authenticated check passed.',
                'checks':[{'kind':'authenticated_provider_api','status':'passed','method':'GET',
                           'endpoint':CHECK_ENDPOINTS['steel'],'checked_at':1700000000}]}

    async def test_native_account_delivery_finishes_without_any_llm(self):
        receipt=self.verified();job=await self.execute(receipt)
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['result']['review']['method'],'deterministic_native_receipt_validation')
        saved=self.root/'work'/job['id']/'account-verification.json'
        self.assertEqual(json.loads(saved.read_text()),receipt)
        self.assertEqual(job['result']['checks'][0]['exit_code'],0)
        self.assertEqual(len(job['result']['files']),2)

    async def test_pending_signup_never_becomes_a_completed_account(self):
        job=await self.execute({'provider':'steel','status':'email_verification_required',
                                'credential_verified':False,'reason':'Email verification pending.'})
        self.assertEqual(job['status'],'blocked');self.assertIn('Email verification',job['error'])
        self.assertNotIn('files',job['result'])

    async def test_success_label_without_authenticated_evidence_is_rejected(self):
        receipt=self.verified();receipt['checks']=[]
        self.assertEqual((await self.execute(receipt))['status'],'failed')

    async def test_wrong_provider_cannot_complete_this_account(self):
        receipt=self.verified();receipt['provider']='firecrawl'
        self.assertEqual((await self.execute(receipt))['status'],'failed')

    async def test_unexpected_secret_field_is_not_written_to_artifacts(self):
        receipt=self.verified();receipt['api_key']='fixture-not-a-real-key'
        job=await self.execute(receipt)
        self.assertEqual(job['status'],'failed')
        self.assertFalse((self.root/'work'/job['id']/'account-verification.json').exists())

    async def test_devhunt_website_profile_completes_without_api_key_or_model(self):
        from account_tools import website_receipt
        receipt=website_receipt({'status':'verified_profile','profile_url':'https://devhunt.org/user/hsk',
            'checked_at':1700000000,'reason':'The saved public profile was reloaded.'})
        job=await self.execute(receipt,provider='devhunt')
        self.assertEqual(job['status'],'completed')
        readme=(self.root/'work'/job['id']/'README.md').read_text()
        self.assertIn('private browser session',readme)
        self.assertNotIn('API confirmed',readme)

    async def test_website_receipt_rejects_foreign_profile_and_secret_query(self):
        from account_tools import website_receipt
        for url in ['https://attacker.invalid/user/hsk','https://devhunt.org/user/hsk?access_token=private']:
            with self.assertRaises(ValueError):
                website_receipt({'status':'verified_profile','profile_url':url})
