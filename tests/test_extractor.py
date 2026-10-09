import unittest
from unittest.mock import patch

from extractor import EMAIL_RE, LINKEDIN_RE, PHONE_RE, _clean_emails, _clean_phones


class ExtractorQualityTests(unittest.TestCase):
    def test_phone_cleanup_keeps_egyptian_numbers_and_rejects_script_numbers(self):
        html = "Call +20 10 1234 5678 or 03 429 2030; ids 1787282933216 and 840000000000001"
        self.assertEqual(
            _clean_phones(PHONE_RE.findall(html)),
            ["+20 10 1234 5678", "03 429 2030"],
        )

    def test_linkedin_extraction_only_accepts_company_pages(self):
        company = "https://www.linkedin.com/company/acme/"
        person = "https://www.linkedin.com/in/person/"
        self.assertEqual(LINKEDIN_RE.search(company).group(0), "https://www.linkedin.com/company/acme")
        self.assertIsNone(LINKEDIN_RE.search(person))

    def test_email_cleanup_blocks_nested_telemetry_domains_without_dns(self):
        values = EMAIL_RE.findall("x@sentry-next.wixpress.com info@example.com")
        with patch("extractor._is_valid_email_domain", return_value=True):
            self.assertEqual(_clean_emails(values), [])


if __name__ == "__main__":
    unittest.main()
