import json
from pathlib import Path
import tempfile
import unittest

from funding_context import context_for_goal, requires_project


class FundingContextTests(unittest.TestCase):
    def test_existing_scope_is_available_without_copying_private_applicant_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'packet.json').write_text(json.dumps({'id':'existing','status':'submitted','program_id':'fixture',
                'draft':{'title':'Route verifier','delivery_plan':['Build route fixtures'],
                         'contact_email':'private@example.org','team':'private legal name','api_key':'private-key'}}))
            context=context_for_goal('Find open grants and build the tool',store=root)
            self.assertEqual(context['existing_applications'][0]['project_scope']['delivery_plan'],['Build route fixtures'])
            self.assertEqual(context['existing_applications'][0]['status'],'submitted')
            text=json.dumps(context)
            self.assertNotIn('private@example.org',text);self.assertNotIn('private legal name',text);self.assertNotIn('private-key',text)

    def test_project_delivery_requirement_does_not_replace_ordinary_grant_research(self):
        self.assertTrue(requires_project('Have a coding agent create the tool for grants'))
        self.assertFalse(requires_project('List open grants'))
        self.assertFalse(requires_project('Build a calendar'))
        self.assertIsNone(context_for_goal('Build a calendar'))

class FundingIntentTests(unittest.TestCase):
    def test_excluded_services_do_not_turn_a_coding_task_into_funding(self):
        from funding_context import is_funding_goal, next_source_tools, context_for_goal, requires_project
        goal = 'Build a CSV tool. Run unittest discover. No grants, RPC, wallets or network is needed.'
        self.assertFalse(is_funding_goal(goal))
        self.assertFalse(requires_project(goal))
        self.assertIsNone(context_for_goal(goal))
        self.assertEqual(next_source_tools(goal, [], {'ingest_tavily': {}}), [])
        self.assertTrue(is_funding_goal('Find open grants and build the project without using an RPC.'))
