"""Tests for the arXiv add (AJAX) and arXiv search API views."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from core.models import PBUser, Paper, Profile
from core.views import _get_or_create_user_corpus


def _fake_result(short_id, title, authors, published):
    """Build a stand-in for an arxiv.Result (only the attrs the view reads)."""
    return SimpleNamespace(
        get_short_id=lambda s=short_id: s,
        title=title,
        authors=[SimpleNamespace(name=n) for n in authors],
        published=published,
    )


class ArxivAddAjaxTests(TestCase):
    """paper_add_arxiv_view AJAX path: single-ID processing, JSON contract."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="arxiv@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(user=self.user, name="P", categories=["cs.AI"])
        self.client.login(username="arxiv@example.com", password="SecurePass123!")

    def _ajax_add(self, profile_id, ids):
        return self.client.post(
            f"/profiles/{profile_id}/add-arxiv/",
            {"arxiv_ids": ids},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @patch("core.views._download_arxiv_pdfs")
    def test_ajax_add_returns_paper_json(self, mock_dl):
        mock_dl.return_value = (1, [])
        Paper.objects.create(source_id="2301.00001", sha256="a" * 64, title="A Great Paper", source="arxiv")
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["paper"]["source_id"], "2301.00001")
        self.assertEqual(data["paper"]["title"], "A Great Paper")
        self.assertEqual(data["paper"]["source"], "arxiv")
        self.assertIn("id", data["paper"])

    @patch("core.views._download_arxiv_pdfs")
    def test_ajax_processes_only_first_id(self, mock_dl):
        mock_dl.return_value = (1, [])
        Paper.objects.create(source_id="2301.00001", sha256="b" * 64, title="First", source="arxiv")
        self._ajax_add(self.profile.pk, "2301.00001, 2301.00002")
        # AJAX handles a single ID: only the first is downloaded.
        self.assertEqual(mock_dl.call_args.args[2], ["2301.00001"])

    def test_ajax_no_valid_ids_returns_400(self):
        resp = self._ajax_add(self.profile.pk, "not-an-arxiv-id")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("core.views._download_arxiv_pdfs")
    def test_ajax_download_failure_returns_400(self, mock_dl):
        mock_dl.return_value = (0, ["2301.00001"])
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("core.views._download_arxiv_pdfs")
    def test_ajax_stored_but_missing_returns_500(self, mock_dl):
        mock_dl.return_value = (1, [])          # reports success but no Paper row exists
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(resp.json()["ok"])

    def test_add_requires_post(self):
        resp = self.client.get(f"/profiles/{self.profile.pk}/add-arxiv/")
        self.assertEqual(resp.status_code, 405)

    def test_add_requires_login(self):
        self.client.logout()
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    @patch("core.views._download_arxiv_pdfs")
    def test_add_other_users_profile_404(self, mock_dl):
        mock_dl.return_value = (1, [])
        other = PBUser.objects.create_user(email="other@example.com", password="SecurePass123!")
        op = Profile.objects.create(user=other, name="OP", categories=["cs.AI"])
        resp = self._ajax_add(op.pk, "2301.00001")
        self.assertEqual(resp.status_code, 404)


class ArxivAddDedupTests(TestCase):
    """Duplicate handling: re-adding the same arXiv ID dedupes by SHA-256."""

    def setUp(self):
        self._paper_storage_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._paper_storage_tmpdir.cleanup)
        self._override_settings = override_settings(
            PAPER_STORAGE_DIR=Path(self._paper_storage_tmpdir.name)
        )
        self._override_settings.enable()
        self.addCleanup(self._override_settings.disable)

        self.user = PBUser.objects.create_user(email="dedup@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(user=self.user, name="P", categories=["cs.AI"])
        self.client.login(username="dedup@example.com", password="SecurePass123!")
    def _ajax_add(self, ids):
        return self.client.post(
            f"/profiles/{self.profile.pk}/add-arxiv/",
            {"arxiv_ids": ids},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @patch("core.views._fetch_arxiv_metadata", return_value={})
    @patch("requests.get")
    def test_ajax_duplicate_arxiv_id_dedupes_by_hash(self, mock_get, _mock_meta):
        resp = Mock()
        resp.content = b"%PDF-1.4 identical bytes for dedup test"
        resp.headers = {"Content-Type": "application/pdf"}
        resp.raise_for_status = Mock()
        mock_get.return_value = resp

        r1 = self._ajax_add("2301.00001")
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["ok"])
        r2 = self._ajax_add("2301.00001")        # same ID -> same bytes -> same hash
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["ok"])
        # Deduplicated: a single Paper row, returned both times.
        self.assertEqual(Paper.objects.filter(source_id="2301.00001").count(), 1)
        self.assertEqual(r1.json()["paper"]["id"], r2.json()["paper"]["id"])


class ArxivSearchApiTests(TestCase):
    """paper_search_arxiv_api_view: validation, response format, rate limit."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="search@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(user=self.user, name="P", categories=["cs.AI"])
        self.client.login(username="search@example.com", password="SecurePass123!")

    def _search(self, **params):
        return self.client.get(f"/profiles/{self.profile.pk}/search-arxiv/", params)

    def test_requires_title_or_author(self):
        resp = self._search()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    @patch("arxiv.Client")
    def test_search_returns_formatted_results(self, mock_client):
        pub = datetime(2023, 1, 15, tzinfo=timezone.utc)
        mock_client.return_value.results.return_value = [
            _fake_result("2301.00001v2", "Deep Learning", ["Alice Smith", "Bob Jones"], pub),
        ]
        resp = self._search(title="deep learning")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["source_id"], "2301.00001")          # version suffix stripped
        self.assertEqual(r["title"], "Deep Learning")
        self.assertEqual(r["authors"], "Alice Smith, Bob Jones")
        self.assertEqual(r["published"], "2023-01-15")
        self.assertFalse(r["already_added"])

    @patch("arxiv.Client")
    def test_search_flags_already_added(self, mock_client):
        corpus = _get_or_create_user_corpus(self.user, self.profile)
        existing = Paper.objects.create(source_id="2301.00001", sha256="c" * 64, title="Existing", source="arxiv")
        existing.corpora.add(corpus)
        pub = datetime(2023, 1, 15, tzinfo=timezone.utc)
        mock_client.return_value.results.return_value = [
            _fake_result("2301.00001v1", "Existing", ["A"], pub),
            _fake_result("2401.99999v1", "New One", ["B"], pub),
        ]
        results = self._search(title="x").json()["results"]
        by_id = {r["source_id"]: r for r in results}
        self.assertTrue(by_id["2301.00001"]["already_added"])
        self.assertFalse(by_id["2401.99999"]["already_added"])

    @patch("arxiv.Client")
    def test_search_truncates_long_author_list(self, mock_client):
        pub = datetime(2023, 1, 15, tzinfo=timezone.utc)
        authors = [f"Author {i}" for i in range(30)]
        mock_client.return_value.results.return_value = [
            _fake_result("2301.00001v1", "Many Authors", authors, pub),
        ]
        r = self._search(title="x").json()["results"][0]
        self.assertTrue(r["authors"].endswith(" et al."))
        self.assertIn("Author 24", r["authors"])       # 25 shown (0..24), then et al.
        self.assertNotIn("Author 25", r["authors"])

    @patch("arxiv.Client")
    def test_second_search_rate_limited(self, mock_client):
        mock_client.return_value.results.return_value = []
        self._search(title="foo")                       # first: allowed
        resp = self._search(title="foo")                # within 3s cooldown
        self.assertEqual(resp.status_code, 429)

    @patch.dict("sys.modules", {"arxiv": None})
    def test_arxiv_not_installed_returns_500(self):
        resp = self._search(title="foo")
        self.assertEqual(resp.status_code, 500)
        self.assertIn("not installed", resp.json()["error"])

    def test_search_requires_login(self):
        self.client.logout()
        resp = self._search(title="foo")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    @patch("arxiv.Client")
    def test_search_other_users_profile_404(self, mock_client):
        mock_client.return_value.results.return_value = []
        other = PBUser.objects.create_user(email="o2@example.com", password="SecurePass123!")
        op = Profile.objects.create(user=other, name="OP", categories=["cs.AI"])
        resp = self.client.get(f"/profiles/{op.pk}/search-arxiv/", {"title": "x"})
        self.assertEqual(resp.status_code, 404)
