"""Verify the boundary before enrichment, Podio checks and persistence."""
import unittest
from unittest.mock import patch

import search_engine


class PipelineTests(unittest.TestCase):
    def test_podio_outage_keeps_company_visible_and_labels_unknown(self):
        report = {}
        candidate = {"name": "Acme", "source": "LinkedIn", "source_url": "https://linkedin.com/company/acme", "snippet": "Headquarters: Alexandria, Egypt"}
        with (
            patch.dict(search_engine.SOURCE_FUNCS, {"LinkedIn": lambda *args: [candidate]}),
            patch.object(search_engine.dedupe, "get_search_offset", return_value=0),
            patch.object(search_engine.dedupe, "advance_search_offset"),
            patch.object(search_engine.dedupe, "company_exists", return_value=False),
            patch.object(search_engine.dedupe, "is_suspect", return_value=False),
            patch.object(search_engine.dedupe, "add_company") as save,
            patch.object(search_engine.dedupe, "add_suspects_to_sheet") as queue,
            patch.object(search_engine.dedupe, "log_search"),
            patch.object(search_engine.dedupe, "sync_to_google_sheets"),
            patch.object(search_engine, "podio_api_precheck", return_value=None),
        ):
            companies, pending = search_engine.process("Software", "Alexandria, Egypt", ["LinkedIn"], 10, run_report=report)
        self.assertEqual(companies, [])
        self.assertEqual([lead["name"] for lead in pending], ["Acme"])
        self.assertEqual(pending[0]["podio_check_status"], "unavailable")
        self.assertIn("unknown", pending[0]["podio_check_reason"])
        self.assertEqual(report["podio_matches"], 0)
        self.assertEqual(report["podio_unavailable"], 1)
        save.assert_not_called()
        queue.assert_called_once_with(pending)

    def test_source_failure_does_not_advance_page_or_run_podio(self):
        report, logs = {}, []
        def fail(*args):
            raise RuntimeError("Search timed out")
        with (
            patch.dict(search_engine.SOURCE_FUNCS, {"LinkedIn": fail}),
            patch.object(search_engine.dedupe, "get_search_offset", return_value=20),
            patch.object(search_engine.dedupe, "advance_search_offset") as advance,
            patch.object(search_engine.dedupe, "log_search"),
            patch.object(search_engine.dedupe, "sync_to_google_sheets"),
            patch.object(search_engine, "podio_api_precheck") as podio,
        ):
            self.assertEqual(search_engine.process("Software", "Alexandria, Egypt", ["LinkedIn"], 10, progress_cb=logs.append, run_report=report), ([], []))
        advance.assert_not_called()
        podio.assert_not_called()
        self.assertEqual(report["source_errors"], {"LinkedIn": "Search timed out"})
        self.assertTrue(any("incomplete" in line for line in logs))

    def test_only_companies_reach_enrichment_and_storage(self):
        candidates = [
            {"name": "Acme Video", "source": "LinkedIn", "source_url": "https://linkedin.com/company/acme-video", "linkedin": "https://linkedin.com/company/acme-video", "snippet": "Headquarters: Alexandria, Egypt"},
            {"name": "Acme Cairo", "source": "LinkedIn", "source_url": "https://linkedin.com/company/acme-cairo", "snippet": "Headquarters: Cairo, Egypt. Serving Alexandria, Egypt."},
            {"name": "Alexandria Agency", "source": "LinkedIn", "source_url": "https://linkedin.com/company/unknown", "location": "Alexandria, Egypt"},
            {"name": "Tutorial", "source": "LinkedIn", "source_url": "https://youtube.com/watch?v=1"},
            {"name": "Vacancy", "source": "LinkedIn", "source_url": "https://linkedin.com/jobs/view/123"},
        ]
        with (
            patch.dict(search_engine.SOURCE_FUNCS, {"LinkedIn": lambda *args: candidates}),
            patch.object(search_engine.dedupe, "get_search_offset", return_value=0),
            patch.object(search_engine.dedupe, "advance_search_offset"),
            patch.object(search_engine.dedupe, "company_exists", return_value=False),
            patch.object(search_engine.dedupe, "is_suspect", return_value=False),
            patch.object(search_engine.dedupe, "add_company") as save,
            patch.object(search_engine.dedupe, "log_search"),
            patch.object(search_engine.dedupe, "sync_to_google_sheets"),
            patch.object(search_engine, "podio_api_precheck", return_value=False) as podio,
        ):
            companies, suspects = search_engine.process("Video Editing", "Alexandria, Egypt", ["LinkedIn"], 10)
        self.assertEqual([lead["name"] for lead in companies], ["Acme Video"])
        self.assertEqual(suspects, [])
        save.assert_called_once()
        podio.assert_called_once_with("Acme Video")
