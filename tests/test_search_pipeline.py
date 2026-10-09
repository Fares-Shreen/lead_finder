"""Verify the boundary before enrichment, Podio checks and persistence."""
import unittest
from unittest.mock import patch

import search_engine


class PipelineTests(unittest.TestCase):
    def test_only_companies_reach_enrichment_and_storage(self):
        candidates = [
            {"name": "Acme Video", "source": "LinkedIn", "source_url": "https://linkedin.com/company/acme-video", "linkedin": "https://linkedin.com/company/acme-video"},
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
