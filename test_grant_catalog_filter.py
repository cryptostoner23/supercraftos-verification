"""The grant catalogue honours the programmes a caller names."""
import unittest

from grant_workflow import grant_catalog


class GrantCatalogFilterTests(unittest.TestCase):
    def test_no_filter_returns_every_programme(self):
        everything = grant_catalog()
        self.assertTrue(everything["programs"])

    def test_a_named_programme_is_the_only_one_returned(self):
        every = grant_catalog()["programs"]
        chosen = every[0]["id"]
        filtered = grant_catalog({"program_ids": [chosen]})["programs"]
        self.assertEqual([row["id"] for row in filtered], [chosen])

    def test_an_unknown_programme_returns_nothing_rather_than_everything(self):
        self.assertEqual(grant_catalog({"program_ids": ["not-a-programme"]})["programs"], [])

    def test_a_malformed_filter_is_rejected(self):
        for bad in ("not-a-list", [1, 2], {"id": "x"}):
            with self.assertRaises(ValueError):
                grant_catalog({"program_ids": bad})


if __name__ == "__main__":
    unittest.main()
