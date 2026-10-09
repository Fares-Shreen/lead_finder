import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import dedupe
from company_location import location_evidence
from lead_quality import sanitize_lead
from sources.google_maps import search_google_maps
from sources.linkedin import search_linkedin_companies


class CompanyLocationTests(unittest.TestCase):
    def test_accepts_english_and_arabic_addresses(self):
        for address in ("12 Street, Smouha, Alexandria, Egypt", "Smouha, Alexandria Governorate, Egypt", "سموحة، الإسكندرية، مصر"):
            with self.subTest(address=address):
                self.assertEqual(location_evidence({"address": address}), address)

    def test_accepts_explicit_profile_location(self):
        for snippet in ("Headquarters: Alexandria, Egypt", "Alexandria, Egypt · Software", "A software company based in Alexandria, Egypt."):
            self.assertTrue(location_evidence({"snippet": snippet}))

    def test_rejects_wrong_or_missing_locations_and_service_area(self):
        for lead in (
            {"name": "Alexandria Agency", "location": "Alexandria, Egypt"},
            {"address": "Alexandria, Virginia, USA"},
            {"address": "Alexandria, Romania"},
            {"address": "Alexandria Road, Cairo, Egypt"},
            {"address": "Cairo, Egypt", "snippet": "Headquarters: Alexandria, Egypt"},
            {"snippet": "Serving customers in Alexandria, Egypt"},
            {"snippet": "Our customers are located in Alexandria, Egypt"},
            {"snippet": "Egyptian company with offices worldwide"},
            {"snippet": "Headquarters: Alexandria"},
        ):
            with self.subTest(lead=lead):
                self.assertEqual(location_evidence(lead), "")

    def test_sanitizer_never_uses_query_location_as_evidence(self):
        lead, reason = sanitize_lead({
            "name": "Alexandria Consulting",
            "source": "LinkedIn",
            "source_url": "https://eg.linkedin.com/company/alexandria-consulting",
            "location": "Alexandria, Egypt",
        })
        self.assertIsNone(lead)
        self.assertIn("location not established", reason)

    @patch("sources.company_profiles._search")
    def test_linkedin_fallback_runs_when_profiles_have_wrong_city(self, search):
        search.side_effect = [
            [{"title": "Cairo Company | LinkedIn", "link": "https://linkedin.com/company/cairo", "snippet": "Headquarters: Cairo, Egypt"}],
            [{"title": "Alex Company | LinkedIn", "link": "https://linkedin.com/company/alex", "snippet": "Headquarters: Alexandria, Egypt"}],
        ]
        leads = search_linkedin_companies("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Alex Company"])
        self.assertEqual(search.call_count, 2)
        for call in search.call_args_list:
            self.assertIn("Egypt", call.args[0])

    @patch("sources.google_maps.requests.get")
    def test_maps_rejects_other_cities_and_missing_addresses(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"local_results": [
            {"title": "Good", "address": "Smouha, Alexandria, Egypt"},
            {"title": "Cairo", "address": "Cairo, Egypt"},
            {"title": "US", "address": "Alexandria, Virginia, USA"},
            {"title": "Unknown"},
        ]}
        get.return_value = response
        leads = search_google_maps("Software", "Alexandria, Egypt", 10, api_key="key")
        self.assertEqual([lead["name"] for lead in leads], ["Good"])
        self.assertEqual(leads[0]["location_evidence"], "Smouha, Alexandria, Egypt")

    def test_location_evidence_survives_database_round_trip(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            with (
                patch.object(dedupe, "DB_PATH", str(Path(directory) / "test.db")),
                patch.object(dedupe, "_CLOUD_SYNC_DONE", True),
            ):
                dedupe.init_db()
                lead = {"name": "Acme", "location": "Alexandria, Egypt", "address": "Smouha, Alexandria, Egypt", "location_evidence": "Smouha, Alexandria, Egypt"}
                dedupe.add_company(lead)
                stored = dedupe.all_companies()[0]
                self.assertEqual(stored["location_evidence"], lead["location_evidence"])
                self.assertEqual(stored["address"], lead["address"])
                # Simulate the old schema and verify additive migration preserves data.
                with dedupe._conn() as con:
                    con.execute("ALTER TABLE companies DROP COLUMN address")
                    con.execute("ALTER TABLE companies DROP COLUMN location_evidence")
                dedupe.init_db()
                self.assertEqual(dedupe.all_companies()[0]["name"], "Acme")
                self.assertEqual(dedupe.all_companies()[0]["location_evidence"], "")
