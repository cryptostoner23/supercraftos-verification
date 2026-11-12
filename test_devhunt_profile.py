import unittest
from unittest.mock import AsyncMock, MagicMock

from devhunt_profile import drive_profile, manage_devhunt_profile, profile_url


class DevhuntProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_login_does_not_demand_api_key_or_submit_profile(self):
        page=MagicMock()
        page.goto=AsyncMock()
        page.locator.return_value.wait_for=AsyncMock()
        page.get_by_role.return_value.count=AsyncMock(return_value=2)
        result=await drive_profile(page,update_name=True)
        self.assertEqual(result['status'],'browser_signin_required')
        self.assertIn('no devhunt api key',result['reason'].lower())
        self.assertEqual(page.goto.await_count,1)
        page.get_by_role.return_value.fill.assert_not_called()

    async def test_arbitrary_urls_and_extra_profile_fields_are_not_accepted(self):
        for arguments in [{'url':'https://attacker.invalid'}, {'update_name':'yes'}, {'real_name':'private'}]:
            with self.assertRaises(ValueError):
                await manage_devhunt_profile(arguments)

    def test_profile_address_cannot_carry_credentials_or_redirect(self):
        self.assertEqual(profile_url('/user/hsk'),'https://devhunt.org/user/hsk')
        for value in ['https://devhunt.org.evil.invalid/user/hsk','https://password@devhunt.org/user/hsk',
                      'https://devhunt.org/user/hsk?token=private','//attacker.invalid/user/hsk','/login']:
            with self.assertRaises(ValueError):profile_url(value)
