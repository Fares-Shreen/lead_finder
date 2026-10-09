import unittest
import requests
from unittest.mock import Mock, patch

from sources.google_maps import search_google_maps
from sources.indeed import search_indeed
from sources.wuzzuf import search_wuzzuf
from sources.linkedin import search_linkedin_companies


def response(payload):
    result = Mock()
    result.status_code = 200
    result.json.return_value = payload
    return result


class SourceContractTests(unittest.TestCase):
    @patch("sources.google_maps.requests.get")
    def test_maps_builds_clickable_link_and_uses_nested_website(self, get):
        get.return_value = response({"local_results": [{
            "title": "Acme",
            "place_id": "123456789",
            "address": "Smouha, Alexandria, Egypt",
            "links": {"website": "https://acme.example"},
        }]})
        lead = search_google_maps("Software", "Alexandria, Egypt", 10, api_key="key")[0]
        self.assertEqual(lead["website"], "https://acme.example")
        self.assertTrue(lead["source_url"].startswith("https://www.google.com/maps/search/"))
        self.assertNotEqual(lead["source_url"], "123456789")

    @patch("sources.serpapi_search.requests.get")
    def test_wuzzuf_keeps_profiles_and_drops_job_pages(self, get):
        get.return_value = response({"organic_results": [
            {"title": "Jobs and Careers at Acme in Egypt", "link": "https://wuzzuf.net/jobs/careers/Acme-Egypt-1", "snippet": "Alexandria, Egypt. Software"},
            {"title": "Developer at Acme", "link": "https://wuzzuf.net/jobs/p/123"},
        ]})
        leads = search_wuzzuf("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme"])

    @patch("sources.serpapi_search.requests.get")
    def test_indeed_keeps_employer_profiles_and_drops_search_pages(self, get):
        get.return_value = response({"organic_results": [
            {"title": "Working at Acme: Reviews", "link": "https://eg.indeed.com/cmp/Acme", "snippet": "Headquarters: Alexandria, Egypt"},
            {"title": "Software jobs", "link": "https://eg.indeed.com/jobs?q=software"},
        ]})
        leads = search_indeed("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme"])

    @patch("sources.company_profiles._search")
    def test_linkedin_falls_back_after_no_company_profiles(self, search):
        search.side_effect = [
            [{"title": "Developer", "link": "https://linkedin.com/jobs/view/123"}],
            [{"title": "Acme Video - LinkedIn", "link": "https://eg.linkedin.com/company/acme-video/about/?trk=test", "snippet": "Headquarters: Alexandria, Egypt"}],
        ]
        leads = search_linkedin_companies("Video Editing", "Alexandria, Egypt", 10, 20, "key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme Video"])
        self.assertEqual(leads[0]["linkedin"], "https://eg.linkedin.com/company/acme-video")
        self.assertEqual(search.call_count, 2)
        for call in search.call_args_list:
            self.assertNotIn('"Alexandria, Egypt"', call.args[0])
            self.assertEqual(call.kwargs["start"], 20)

    @patch("sources.company_profiles._search")
    def test_profile_search_drops_spoofed_domains_posts_and_home_page(self, search):
        search.return_value = [
            {"title": "Acme", "link": "https://linkedin.com.evil.example/company/acme"},
            {"title": "Acme", "link": "https://linkedin.com/company/acme/posts/123"},
            {"title": "Acme", "link": "https://youtube.com/company/acme"},
            {"title": "Acme", "link": "https://linkedin.com/company/acme", "snippet": "Headquarters: Alexandria, Egypt"},
            {"title": "Acme", "link": "https://linkedin.com/company/acme?trk=duplicate", "snippet": "Headquarters: Alexandria, Egypt"},
        ]
        leads = search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["linkedin"], "https://linkedin.com/company/acme")

    @patch("sources.serpapi_search.requests.get")
    def test_api_error_is_reported_instead_of_empty_companies(self, get):
        get.return_value = response({"error": "Monthly quota exceeded"})
        with self.assertRaisesRegex(RuntimeError, "Monthly quota exceeded"):
            search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual(get.call_count, 1)

    @patch("sources.serpapi_search.requests.get")
    def test_http_auth_error_keeps_provider_message_without_exposing_key(self, get):
        get.return_value = response({"error": "Invalid API key private-key"})
        get.return_value.status_code = 401
        with self.assertRaisesRegex(RuntimeError, "Invalid API key") as caught:
            search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="private-key")
        self.assertNotIn("private-key", str(caught.exception))

    @patch("sources.serpapi_search.requests.get")
    def test_linkedin_recovers_from_transient_timeout(self, get):
        get.side_effect = [requests.Timeout("secret request URL"), response({"organic_results": [
            {"title": "Acme | LinkedIn", "link": "https://linkedin.com/company/acme", "snippet": "Headquarters: Alexandria, Egypt"},
        ]})]
        leads = search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="private-key")
        self.assertEqual([lead["name"] for lead in leads], ["Acme"])
        self.assertEqual(get.call_count, 2)

    @patch("sources.serpapi_search.requests.get")
    def test_persistent_timeout_is_reported_safely(self, get):
        get.side_effect = requests.Timeout("https://serpapi.com?api_key=private-key")
        with self.assertRaisesRegex(RuntimeError, "timed out after two attempts") as caught:
            search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="private-key")
        self.assertEqual(get.call_count, 2)
        self.assertNotIn("private-key", str(caught.exception))

    @patch("sources.serpapi_search.requests.get")
    def test_connection_failure_is_distinct_from_auth_error(self, get):
        get.side_effect = requests.ConnectionError("private-key")
        with self.assertRaisesRegex(RuntimeError, "Unable to connect"):
            search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="private-key")
        self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
