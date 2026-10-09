import unittest
from unittest.mock import patch

from lead_quality import sanitize_lead
from sources.company_profiles import search_company_profiles
from sources.location_verifier import verify_on_maps


PLACE = {"name": "Acme Ltd", "address": "Smouha, Alexandria, Egypt",
         "source_url": "https://www.google.com/maps/search/?api=1&query=Acme"}


class LocationVerifierTests(unittest.TestCase):
    @patch("sources.location_verifier.search_google_maps")
    def test_exact_normalized_name_and_address_required(self, maps):
        maps.return_value = [dict(PLACE, name="Acme Other"), dict(PLACE, address="Cairo, Egypt")]
        self.assertIsNone(verify_on_maps("Acme", "key"))
        maps.return_value.append(PLACE)
        self.assertEqual(verify_on_maps("Acme", "key"), PLACE)

    @patch("sources.company_profiles.verify_on_maps", return_value=PLACE)
    @patch("sources.company_profiles._search")
    def test_missing_snippet_location_can_be_verified_on_maps(self, search, maps):
        search.return_value = [{"title": "Acme | LinkedIn",
                                "link": "https://linkedin.com/company/acme",
                                "snippet": "Software development company"}]
        leads = search_company_profiles("LinkedIn", "IT", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["address"], PLACE["address"])
        self.assertIn(PLACE["source_url"], leads[0]["location_evidence"])
        cleaned, reason = sanitize_lead(leads[0])
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned["location_evidence"].count("Maps:"), 1)

    @patch("sources.company_profiles.verify_on_maps", side_effect=RuntimeError("unavailable"))
    @patch("sources.company_profiles._search")
    def test_verification_failures_do_not_invent_location_and_are_bounded(self, search, maps):
        search.return_value = [{"title": f"Company {i} | LinkedIn",
                                "link": f"https://linkedin.com/company/company-{i}",
                                "snippet": "Software company"} for i in range(5)]
        leads = search_company_profiles("LinkedIn", "IT", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual(leads, [])
        self.assertEqual(maps.call_count, 2)
        self.assertEqual(leads.diagnostics["Maps checks unavailable"], 2)
        self.assertEqual(search.call_count, 3)

