import unittest
from unittest.mock import Mock, patch

from sources.google_maps import search_google_maps
from sources.indeed import search_indeed
from sources.wuzzuf import search_wuzzuf


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


class SourceContractTests(unittest.TestCase):
    @patch("sources.google_maps.requests.get")
    def test_maps_builds_clickable_link_and_uses_nested_website(self, get):
        get.return_value = response({"local_results": [{
            "title": "Acme",
            "place_id": "123456789",
            "links": {"website": "https://acme.example"},
        }]})
        lead = search_google_maps("Software", "Alexandria, Egypt", 10, api_key="key")[0]
        self.assertEqual(lead["website"], "https://acme.example")
        self.assertTrue(lead["source_url"].startswith("https://www.google.com/maps/search/"))
        self.assertNotEqual(lead["source_url"], "123456789")

    @patch("sources.wuzzuf.requests.get")
    def test_wuzzuf_keeps_profiles_and_drops_job_pages(self, get):
        get.return_value = response({"organic_results": [
            {"title": "Jobs and Careers at Acme in Egypt", "link": "https://wuzzuf.net/jobs/careers/Acme-Egypt-1"},
            {"title": "Developer at Acme", "link": "https://wuzzuf.net/jobs/p/123"},
        ]})
        leads = search_wuzzuf("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme"])

    @patch("sources.indeed.requests.get")
    def test_indeed_keeps_employer_profiles_and_drops_search_pages(self, get):
        get.return_value = response({"organic_results": [
            {"title": "Working at Acme: Reviews", "link": "https://eg.indeed.com/cmp/Acme"},
            {"title": "Software jobs", "link": "https://eg.indeed.com/jobs?q=software"},
        ]})
        leads = search_indeed("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme"])


if __name__ == "__main__":
    unittest.main()
