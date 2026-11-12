import os
import unittest
from unittest.mock import patch

from gmail_mailbox import GmailMailbox


class FakeIMAP:
    def __init__(self, host, port, timeout):
        assert (host, port, timeout) == ("imap.gmail.com", 993, 20)
        self.password = None
        self.readonly = None

    def login(self, address, password):
        self.password = password

    def select(self, name, readonly):
        self.readonly = readonly
        return "OK", [b"1"]

    def search(self, *args):
        return "OK", [b"1"]

    def fetch(self, *args):
        return "OK", [(b"1", b"From: Firecrawl <noreply@firecrawl.dev>\nSubject: Verify Firecrawl\nContent-Type: text/plain\n\nOpen https://firecrawl.dev/verify?id=fixture")]

    def logout(self):
        return "BYE", []


class GmailMailboxTests(unittest.TestCase):
    def test_backend_uses_only_app_password_and_readonly_mailbox(self):
        fake = FakeIMAP("imap.gmail.com", 993, 20)
        with patch.dict(os.environ, {"GMAIL_ADDRESS": "fixture@gmail.com", "GMAIL_APP_PASSWORD": "fixture-app-password", "GMAIL_LOGIN_PASSWORD": "web-password", "GMAIL_OAUTH_ACCESS_TOKEN": ""}):
            result = GmailMailbox(lambda *args, **kwargs: fake).search()
        self.assertEqual(fake.password, "fixture-app-password")
        self.assertTrue(fake.readonly)
        self.assertEqual(result[0]["links"], ["https://firecrawl.dev/verify?id=fixture"])

    def test_web_password_is_not_used_for_imap(self):
        with patch.dict(os.environ, {"GMAIL_ADDRESS": "fixture@gmail.com", "GMAIL_APP_PASSWORD": "", "GMAIL_OAUTH_ACCESS_TOKEN": "", "GMAIL_LOGIN_PASSWORD": "web-password"}):
            with self.assertRaisesRegex(RuntimeError, "GMAIL_APP_PASSWORD"):
                GmailMailbox().search()
