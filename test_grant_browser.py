import unittest
from grant_browser import form_answers,FORM_URL
from grant_submission import adapter_for

class GrantBrowserTests(unittest.TestCase):
    def packet(self):
        return {'draft':{'title':'Public route fixtures','proposed_solution':'Proposed read-only fixtures.',
          'public_goods_case':'Reproducible public evidence.','team':'Public maintainer',
          'delivery_plan':['Publish fixtures'],'repository_url':'https://github.com/owner/project',
          'budget_usd':7500,'budget_breakdown_usd':{'implementation':5000,'documentation':2500},
          'success_metrics':['Public test release']}}
    def test_no_invented_legal_identity_or_live_metrics(self):
        answers,missing=form_answers(self.packet(),{'GMAIL_ADDRESS':'owner@actual-domain.org'})
        self.assertEqual(missing,[]);self.assertEqual(answers['First Name'],'owner')
        self.assertIn('public pseudonym',answers['Last Name'])
        self.assertIn('no live TVL',answers['What are your most relevant metrics? (TVL, volume, users, revenue — whatever applies)'])
    def test_missing_contact_and_inconsistent_budget_are_not_sent(self):
        value=self.packet();value['draft']['budget_usd']=1000
        _,missing=form_answers(value,{})
        self.assertIn('contact_email',missing);self.assertIn('itemized_budget_matching_total',missing)
    def test_only_the_verified_official_form_uses_browser_adapter(self):
        adapter=adapter_for({'id':'uniswap-foundation-grants','application_url':FORM_URL},environ={})
        self.assertEqual(adapter.provider,'official_notion_form')
        self.assertIsNone(adapter_for({'id':'uniswap-foundation-grants','application_url':'https://attacker.example/form'},environ={}))
    def test_transport_status_alone_cannot_fabricate_a_browser_submission(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        from grant_browser import OfficialNotionGrantAdapter
        package={**self.packet(),'id':'packet-1'}
        adapter=OfficialNotionGrantAdapter({'GMAIL_ADDRESS':'owner@actual-domain.org'})
        with patch('grant_browser.subprocess.run',return_value=SimpleNamespace(stdout=json.dumps({'status':'submitted'}))):
            result=adapter.submit(package,{},'attempt-1')
        self.assertEqual(result.status,'verification_required')
    def test_provider_confirmation_keeps_actual_text_without_inventing_receipt_id(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import patch
        from grant_browser import OfficialNotionGrantAdapter
        package={**self.packet(),'id':'packet-1'}
        adapter=OfficialNotionGrantAdapter({'GMAIL_ADDRESS':'owner@actual-domain.org'})
        receipt={'receipt_type':'visible_provider_confirmation','form_url':FORM_URL,
                 'provider_confirmation':'Thanks for filling this out!','provider_receipt_id':None}
        with patch('grant_browser.subprocess.run',return_value=SimpleNamespace(stdout=json.dumps({'status':'submitted','receipt':receipt}))):
            result=adapter.submit(package,{},'attempt-1')
        self.assertEqual(result.status,'submitted');self.assertIsNone(result.receipt['provider_receipt_id'])
    def test_saved_application_exposes_real_confirmation_without_contact_data(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        import grant_workflow
        with tempfile.TemporaryDirectory() as root:
            packet={'id':'9be6c6aa-ba2c-4283-bc74-834583de2504','status':'submitted',
                    'draft':{'title':'Open fixtures','contact_email':'private@actual-domain.org'},
                    'submission':{'status':'submitted','receipt':{'provider_confirmation':'Your response has been submitted.'}}}
            Path(root,packet['id']+'.json').write_text(json.dumps(packet))
            with patch.object(grant_workflow,'STORE',Path(root)):result=grant_workflow.saved_grant_applications()
        self.assertEqual(result['packages'][0]['status'],'submitted')
        self.assertNotIn('private@actual-domain.org',json.dumps(result))
        self.assertIn('Your response has been submitted.',json.dumps(result))
    def test_itemized_budget_survives_normal_profile_drafting(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import grant_workflow
        profile={'project_name':'Fixtures','summary':'Read-only public fixtures','budget_usd':7500,
                 'budget_breakdown_usd':{'implementation':5000,'docs':2500}}
        with tempfile.TemporaryDirectory() as root,patch.object(grant_workflow,'STORE',Path(root)):
            packet=grant_workflow.draft_grant_application({'program_id':'uniswap-foundation-grants','profile':profile})
        self.assertEqual(packet['draft']['budget_breakdown_usd'],profile['budget_breakdown_usd'])

    def test_public_alias_overrides_legal_names_without_disclosing_them(self):
        packet=self.packet()
        packet['draft'].update(contact_first_name='Private',contact_last_name='Legal Identity')
        answers,missing=form_answers(packet,{}, {'public_name':'HSK','contact_email':'owner@actual-domain.org','legal_name':'Private Legal Identity'})
        self.assertEqual(missing,[])
        self.assertEqual(answers['First Name'],'HSK')
        self.assertEqual(answers['Email'],'owner@actual-domain.org')
        self.assertNotIn('Private Legal Identity',str(answers))
        self.assertIn('public pseudonym',answers['Last Name'])
