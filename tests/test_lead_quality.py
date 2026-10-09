import unittest

from lead_quality import (
    is_useful_company_name,
    is_useful_company_website,
    is_valid_source_url,
    normalize_url,
    sanitize_lead,
)


class LeadQualityTests(unittest.TestCase):
    def test_rejects_video_social_and_content_sites_as_company_websites(self):
        for url in (
            "https://youtube.com/watch?v=123",
            "https://youtu.be/123",
            "https://facebook.com/example",
            "https://en.wikipedia.org/wiki/Example",
            "https://medium.com/@example/article",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_useful_company_website(url))

    def test_accepts_company_owned_website(self):
        self.assertTrue(is_useful_company_website("https://example-company.com/about"))

    def test_unwraps_google_redirect(self):
        wrapped = "https://www.google.com/url?q=https%3A%2F%2Facme.example%2Fabout&sa=U"
        self.assertEqual(normalize_url(wrapped), "https://acme.example/about")

    def test_source_urls_must_be_company_or_place_pages(self):
        self.assertTrue(is_valid_source_url("LinkedIn", "https://eg.linkedin.com/company/acme"))
        self.assertFalse(is_valid_source_url("LinkedIn", "https://linkedin.com/jobs/view/123"))
        self.assertTrue(is_valid_source_url("Wuzzuf", "https://wuzzuf.net/jobs/careers/Acme-Egypt-1"))
        self.assertFalse(is_valid_source_url("Wuzzuf", "https://wuzzuf.net/jobs/p/123"))
        self.assertTrue(is_valid_source_url("Indeed", "https://eg.indeed.com/cmp/Acme"))
        self.assertFalse(is_valid_source_url("Indeed", "https://eg.indeed.com/jobs?q=software"))
        self.assertFalse(is_valid_source_url("Google Maps", "ChIJ-not-a-clickable-url"))

    def test_sanitize_removes_bad_website_but_keeps_valid_lead(self):
        lead, reason = sanitize_lead({
            "name": "Acme",
            "source": "LinkedIn",
            "source_url": "https://linkedin.com/company/acme",
            "linkedin": "https://linkedin.com/company/acme",
            "website": "https://youtube.com/@acme",
        })
        self.assertEqual(reason, "")
        self.assertEqual(lead["website"], "")
        self.assertEqual(lead["linkedin"], "https://linkedin.com/company/acme")

    def test_sanitize_rejects_wrong_source_page(self):
        lead, reason = sanitize_lead({
            "name": "Ten Great Software Companies",
            "source": "Indeed",
            "source_url": "https://youtube.com/watch?v=123",
        })
        self.assertIsNone(lead)
        self.assertTrue(reason)

    def test_rejects_listicle_and_search_titles(self):
        for name in ("Top 10 Software Firms", "20 Best Agencies", "Software Companies in Cairo"):
            with self.subTest(name=name):
                self.assertFalse(is_useful_company_name(name))


if __name__ == "__main__":
    unittest.main()
