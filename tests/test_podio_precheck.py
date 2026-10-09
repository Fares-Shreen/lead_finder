import unittest
from unittest.mock import patch

from podio_check import check_podio
from search_engine import podio_api_precheck


class PodioPrecheckTests(unittest.TestCase):
    @patch("podio_check.raw_podio_response")
    def test_unrelated_search_hits_are_not_duplicates(self, response):
        response.return_value = [{"name": "app", "contents": [{"title": "Another Company"}]}]
        self.assertEqual(check_podio("Acme")["status"], "no_match")
        self.assertIs(podio_api_precheck("Acme"), False)

    @patch("podio_check.raw_podio_response")
    def test_exact_normalized_match_requires_review(self, response):
        response.return_value = [{"name": "app", "contents": [{"title": " ACME   Company "}]}]
        self.assertEqual(check_podio("Acme Company")["status"], "match")
        self.assertIs(podio_api_precheck("Acme Company"), True)

    @patch("podio_check.raw_podio_response")
    def test_unavailable_and_malformed_results_are_unknown(self, response):
        for data in (None, {}, [{"error": "unavailable"}], [{"contents": [{"unexpected": "value"}]}]):
            with self.subTest(data=data):
                response.return_value = data
                self.assertEqual(check_podio("Acme")["status"], "unknown")
                self.assertIsNone(podio_api_precheck("Acme"))

    @patch("podio_check.raw_podio_response", return_value=[])
    def test_empty_successful_results_have_no_match(self, response):
        self.assertIs(podio_api_precheck("Acme"), False)
