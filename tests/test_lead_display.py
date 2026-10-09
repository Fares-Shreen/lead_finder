import unittest

from lead_display import DISCOVERY_COLUMNS, discovery_frame


class DiscoveryDisplayTests(unittest.TestCase):
    def test_old_records_missing_entire_columns_do_not_crash(self):
        frame = discovery_frame([{"name": "Acme", "source": "Google Maps"}])
        self.assertEqual(list(frame.columns), DISCOVERY_COLUMNS)
        self.assertEqual(frame.iloc[0]["name"], "Acme")
        self.assertEqual(frame.iloc[0]["location_evidence"], "")
        self.assertEqual(frame.iloc[0]["location"], "")

    def test_mixed_records_keep_evidence_and_normalize_null_values(self):
        frame = discovery_frame([
            {"name": "Acme", "location_evidence": "Smouha, Alexandria, Egypt"},
            {"name": "Older", "website": None},
        ])
        self.assertEqual(frame.iloc[0]["location_evidence"], "Smouha, Alexandria, Egypt")
        self.assertEqual(frame.iloc[1]["location_evidence"], "")
        self.assertEqual(frame.iloc[1]["website"], "")

    def test_empty_results_have_the_display_schema(self):
        frame = discovery_frame([])
        self.assertTrue(frame.empty)
        self.assertEqual(list(frame.columns), DISCOVERY_COLUMNS)
