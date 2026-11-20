"""The search API through the Europe PMC provider, with the provider mocked."""

import os
from unittest.mock import AsyncMock, patch

from django.test import TestCase
from preprint_sources import EuropePmcSearchProvider, PaperEntry

from core.models import PBUser, Profile


def _entry(source, doi):
    return PaperEntry(
        source_id=doi,
        title="A preprint",
        abstract="",
        url=f"https://doi.org/{doi}",
        pdf_url="",
        authors=["Swarna NP", "Pachter L"],
        categories=[],
        published="2026-11-18",
        source=source,
    )


@patch.dict(os.environ, {"PREPRINT_ENABLED_SOURCES": "arxiv,biorxiv"})
class EuropePmcSearchApiTests(TestCase):
    def setUp(self):
        self.user = PBUser.objects.create_user(email="epmc@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(
            user=self.user, name="P", source_categories={"biorxiv": ["genetics"]}
        )
        self.client.login(username="epmc@example.com", password="SecurePass123!")

    @patch.object(
        EuropePmcSearchProvider,
        "search",
        new_callable=AsyncMock,
        return_value=[
            _entry("biorxiv", "10.64898/2026.11.16.767160"),
            _entry("medrxiv", "10.64898/2026.11.11.26367525"),
        ],
    )
    def test_searches_enabled_servers_and_links_results(self, mock_search):
        resp = self.client.get(
            f"/profiles/{self.profile.pk}/search/", {"title": "x", "provider": "europepmc"}
        )
        self.assertEqual(resp.status_code, 200)
        # Only the enabled server is asked for...
        self.assertEqual(mock_search.await_args.kwargs["sources"], ["biorxiv"])
        payload = resp.json()
        self.assertEqual(payload["provider"], "europepmc")
        self.assertEqual(payload["label"], "Europe PMC")
        # ...and anything else that comes back is dropped.
        [result] = payload["results"]
        self.assertEqual(result["source"], "biorxiv")
        self.assertEqual(result["source_label"], "bioRxiv")
        self.assertEqual(
            result["landing_url"], "https://www.biorxiv.org/content/10.64898/2026.11.16.767160"
        )
        self.assertEqual(result["published"], "2026-11-18")

    def test_search_tab_offers_both_providers(self):
        resp = self.client.get("/profiles/")
        self.assertContains(resp, '<option value="europepmc">Europe PMC (bioRxiv)</option>')
        self.assertContains(resp, '<option value="arxiv">arXiv</option>')
