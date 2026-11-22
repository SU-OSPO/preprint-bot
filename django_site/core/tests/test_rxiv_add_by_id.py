"""Add-by-ID through the bioRxiv/medRxiv sources, with their API and PDF host mocked."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from django.test import TestCase, override_settings
from preprint_sources import BiorxivSource
from preprint_sources.rxiv import _entry_from_versions

from core.models import PBUser, Paper, Profile

DOI = "10.64898/2026.10.13.758934"


def _versions(*versions):
    """API version records for DOI, one per (version, posting date) pair."""
    return [
        {
            "doi": DOI,
            "title": "scRBP infers regulons",
            "authors": "Ma, Y.; Tang, M.",
            "date": date,
            "version": version,
            "category": "genetics",
            "abstract": "Body.",
        }
        for version, date in versions
    ]


@patch.dict(os.environ, {"PREPRINT_ENABLED_SOURCES": "arxiv,biorxiv,medrxiv"})
class RxivAddByIdTests(TestCase):
    def setUp(self):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        storage = override_settings(PAPER_STORAGE_DIR=Path(tmpdir.name))
        storage.enable()
        self.addCleanup(storage.disable)

        self.user = PBUser.objects.create_user(email="rxiv@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(
            user=self.user, name="P", source_categories={"biorxiv": ["genetics"]}
        )
        self.client.login(username="rxiv@example.com", password="SecurePass123!")

    def _ajax_add(self, ids, source):
        return self.client.post(
            f"/profiles/{self.profile.pk}/add-by-id/",
            {"source_ids": ids, "source": source},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @patch.object(
        BiorxivSource,
        "fetch_one",
        new=AsyncMock(
            return_value=_entry_from_versions(
                _versions(("1", "2026-10-19"), ("2", "2026-11-02")),
                "https://www.biorxiv.org",
                "biorxiv",
            )
        ),
    )
    @patch("requests.get")
    def test_adds_latest_version_from_a_biorxiv_url(self, mock_get):
        mock_get.return_value = Mock(
            content=b"%PDF-1.4 a bioRxiv paper",
            headers={"Content-Type": "application/pdf"},
            raise_for_status=Mock(),
        )
        resp = self._ajax_add(f"https://www.biorxiv.org/content/{DOI}v1.full", "biorxiv")

        self.assertEqual(resp.status_code, 200)
        paper = resp.json()["paper"]
        self.assertEqual(paper["source"], "biorxiv")
        self.assertEqual(paper["source_id"], DOI)
        self.assertEqual(paper["landing_url"], f"https://www.biorxiv.org/content/{DOI}")
        # The newest version's PDF, dated by the first version's posting day
        self.assertEqual(
            mock_get.call_args.args[0], f"https://www.biorxiv.org/content/{DOI}v2.full.pdf"
        )
        stored = Paper.objects.get(pk=paper["id"])
        self.assertEqual(stored.submitted_date.date().isoformat(), "2026-10-19")

    @patch("requests.get")
    def test_other_servers_url_is_not_a_valid_id(self, mock_get):
        resp = self._ajax_add(f"https://www.medrxiv.org/content/{DOI}v1", "biorxiv")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No valid bioRxiv IDs", resp.json()["error"])
        mock_get.assert_not_called()

    def test_add_tab_offers_both_rxiv_servers(self):
        resp = self.client.get("/profiles/")
        self.assertContains(resp, 'data-tab="byid-')
        self.assertContains(resp, ">bioRxiv</option>")
        self.assertContains(resp, ">medRxiv</option>")
