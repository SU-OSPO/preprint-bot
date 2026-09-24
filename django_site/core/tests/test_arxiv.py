"""Tests for the add-by-ID (AJAX) and source search API views.

Both views are source-generic; these exercise them through the arXiv source,
which is the one every deployment enables by default.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from django.test import TestCase, override_settings
from preprint_sources import ArxivSource, PaperEntry

from core.models import PBUser, Paper, Profile
from core.views import _compute_sha256, _get_or_create_user_corpus


def _entry(source_id, title, authors, published="2023-01-15T00:00:00Z"):
    """Build a PaperEntry the way ArxivSource would return one."""
    return PaperEntry(
        source_id=source_id,
        title=title,
        abstract="An abstract.",
        # arXiv's Atom API really does report ids as non-TLS, version-pinned
        # URLs; keeping that shape here guards the landing_url handling.
        url=f"http://arxiv.org/abs/{source_id}v1",
        pdf_url=f"https://arxiv.org/pdf/{source_id}.pdf",
        authors=list(authors),
        categories=["cs.AI"],
        published=published,
        source="arxiv",
    )


class AddByIdAjaxTests(TestCase):
    """paper_add_by_id_view AJAX path: single-ID processing, JSON contract."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="arxiv@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(
            user=self.user, name="P", source_categories={"arxiv": ["cs.AI"]}
        )
        self.client.login(username="arxiv@example.com", password="SecurePass123!")

    def _ajax_add(self, profile_id, ids, source="arxiv"):
        return self.client.post(
            f"/profiles/{profile_id}/add-by-id/",
            {"source_ids": ids, "source": source},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @patch("core.views._download_source_papers")
    def test_ajax_add_returns_paper_json(self, mock_dl):
        paper = Paper.objects.create(
            source_id="2301.00001", sha256="a" * 64, title="A Great Paper", source="arxiv"
        )
        mock_dl.return_value = ([paper], [])
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["paper"]["source_id"], "2301.00001")
        self.assertEqual(data["paper"]["title"], "A Great Paper")
        self.assertEqual(data["paper"]["source"], "arxiv")
        self.assertEqual(data["paper"]["source_label"], "arXiv")
        self.assertEqual(data["paper"]["landing_url"], "https://arxiv.org/abs/2301.00001")
        self.assertIn("id", data["paper"])

    @patch("core.views._download_source_papers")
    def test_ajax_processes_only_first_id(self, mock_dl):
        paper = Paper.objects.create(
            source_id="2301.00001", sha256="b" * 64, title="First", source="arxiv"
        )
        mock_dl.return_value = ([paper], [])
        self._ajax_add(self.profile.pk, "2301.00001, 2301.00002")
        # AJAX handles a single ID: only the first is downloaded.
        self.assertEqual(mock_dl.call_args.args[3], ["2301.00001"])

    @patch("core.views._download_source_papers")
    def test_ajax_uses_named_source(self, mock_dl):
        paper = Paper.objects.create(
            source_id="2301.00001", sha256="e" * 64, title="First", source="arxiv"
        )
        mock_dl.return_value = ([paper], [])
        self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(mock_dl.call_args.args[2].name, "arxiv")

    def test_ajax_unknown_source_returns_400(self):
        resp = self._ajax_add(self.profile.pk, "2301.00001", source="not-a-source")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_ajax_no_valid_ids_returns_400(self):
        resp = self._ajax_add(self.profile.pk, "not-an-arxiv-id")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("core.views._download_source_papers")
    def test_ajax_download_failure_returns_400(self, mock_dl):
        mock_dl.return_value = ([], ["2301.00001"])
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    @patch("core.views._download_source_papers")
    def test_ajax_nothing_linked_returns_400(self, mock_dl):
        mock_dl.return_value = ([], [])  # neither linked nor reported failed
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_add_requires_post(self):
        resp = self.client.get(f"/profiles/{self.profile.pk}/add-by-id/")
        self.assertEqual(resp.status_code, 405)

    def test_add_requires_login(self):
        self.client.logout()
        resp = self._ajax_add(self.profile.pk, "2301.00001")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    @patch("core.views._download_source_papers")
    def test_add_other_users_profile_404(self, mock_dl):
        mock_dl.return_value = ([], [])
        other = PBUser.objects.create_user(email="other@example.com", password="SecurePass123!")
        op = Profile.objects.create(user=other, name="OP", source_categories={"arxiv": ["cs.AI"]})
        resp = self._ajax_add(op.pk, "2301.00001")
        self.assertEqual(resp.status_code, 404)


class AddByIdDedupTests(TestCase):
    """Duplicate handling: re-adding the same ID dedupes by SHA-256."""

    def setUp(self):
        self._paper_storage_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._paper_storage_tmpdir.cleanup)
        self._override_settings = override_settings(
            PAPER_STORAGE_DIR=Path(self._paper_storage_tmpdir.name)
        )
        self._override_settings.enable()
        self.addCleanup(self._override_settings.disable)

        self.user = PBUser.objects.create_user(email="dedup@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(
            user=self.user, name="P", source_categories={"arxiv": ["cs.AI"]}
        )
        self.client.login(username="dedup@example.com", password="SecurePass123!")

    def _ajax_add(self, ids):
        return self.client.post(
            f"/profiles/{self.profile.pk}/add-by-id/",
            {"source_ids": ids, "source": "arxiv"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    @patch.object(
        ArxivSource,
        "fetch_many",
        new=AsyncMock(return_value={"2301.00001": _entry("2301.00001", "Dedup Me", ["A"])}),
    )
    @patch("requests.get")
    def test_ajax_duplicate_id_dedupes_by_hash(self, mock_get):
        resp = Mock()
        resp.content = b"%PDF-1.4 identical bytes for dedup test"
        resp.headers = {"Content-Type": "application/pdf"}
        resp.raise_for_status = Mock()
        mock_get.return_value = resp

        r1 = self._ajax_add("2301.00001")
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["ok"])
        r2 = self._ajax_add("2301.00001")  # same ID -> same bytes -> same hash
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["ok"])
        # Deduplicated: a single Paper row, returned both times.
        self.assertEqual(Paper.objects.filter(source_id="2301.00001").count(), 1)
        self.assertEqual(r1.json()["paper"]["id"], r2.json()["paper"]["id"])

    @patch.object(
        ArxivSource,
        "fetch_many",
        new=AsyncMock(return_value={"2301.00001": _entry("2301.00001", "Dedup Me", ["A"])}),
    )
    @patch("requests.get")
    def test_dedup_against_user_upload_still_succeeds(self, mock_get):
        """A hand-uploaded copy of the same PDF must not turn the add into a 500.

        SHA-256 dedup links the row that already holds those bytes — here an
        upload whose source is "user" and whose source_id is None — so the
        response has to describe the row that was linked rather than be looked
        up by the requested source and id.
        """
        pdf = b"%PDF-1.4 bytes already uploaded by hand"
        upload = Paper.objects.create(
            title="Hand upload",
            sha256=_compute_sha256(pdf),
            source="user",
        )
        resp = Mock()
        resp.content = pdf
        resp.headers = {"Content-Type": "application/pdf"}
        resp.raise_for_status = Mock()
        mock_get.return_value = resp

        r = self._ajax_add("2301.00001")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        # The existing upload is what got linked — no second row, no 500.
        self.assertEqual(r.json()["paper"]["id"], upload.pk)
        self.assertEqual(r.json()["paper"]["source_label"], "User upload")
        self.assertEqual(Paper.objects.count(), 1)

    @patch.object(ArxivSource, "fetch_many", new=AsyncMock(return_value={}))
    @patch("requests.get")
    def test_unknown_id_fails_without_downloading(self, mock_get):
        resp = self._ajax_add("2301.00001")
        self.assertEqual(resp.status_code, 400)
        mock_get.assert_not_called()


class SearchApiTests(TestCase):
    """paper_search_api_view: validation, response format, rate limit."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="search@example.com", password="SecurePass123!"
        )
        self.profile = Profile.objects.create(
            user=self.user, name="P", source_categories={"arxiv": ["cs.AI"]}
        )
        self.client.login(username="search@example.com", password="SecurePass123!")

    def _search(self, **params):
        return self.client.get(f"/profiles/{self.profile.pk}/search/", params)

    def test_requires_title_or_author(self):
        resp = self._search()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_unknown_source_returns_400(self):
        resp = self._search(title="x", source="not-a-source")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    @patch.object(
        ArxivSource,
        "search",
        new=AsyncMock(
            return_value=[_entry("2301.00001", "Deep Learning", ["Alice Smith", "Bob Jones"])]
        ),
    )
    def test_search_returns_formatted_results(self):
        resp = self._search(title="deep learning")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["source"], "arxiv")
        self.assertEqual(payload["label"], "arXiv")
        results = payload["results"]
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["source_id"], "2301.00001")
        self.assertEqual(r["title"], "Deep Learning")
        self.assertEqual(r["authors"], "Alice Smith, Bob Jones")
        self.assertEqual(r["published"], "2023-01-15")
        self.assertEqual(r["landing_url"], "https://arxiv.org/abs/2301.00001")
        self.assertFalse(r["already_added"])

    @patch.object(
        ArxivSource,
        "search",
        new=AsyncMock(
            return_value=[
                _entry("2301.00001", "Existing", ["A"]),
                _entry("2401.99999", "New One", ["B"]),
            ]
        ),
    )
    def test_search_flags_already_added(self):
        corpus = _get_or_create_user_corpus(self.user, self.profile)
        existing = Paper.objects.create(
            source_id="2301.00001", sha256="c" * 64, title="Existing", source="arxiv"
        )
        existing.corpora.add(corpus)
        results = self._search(title="x").json()["results"]
        by_id = {r["source_id"]: r for r in results}
        self.assertTrue(by_id["2301.00001"]["already_added"])
        self.assertFalse(by_id["2401.99999"]["already_added"])

    @patch.object(
        ArxivSource,
        "search",
        new=AsyncMock(
            return_value=[
                _entry("2301.00001", "Many Authors", [f"Author {i}" for i in range(30)]),
            ]
        ),
    )
    def test_search_truncates_long_author_list(self):
        r = self._search(title="x").json()["results"][0]
        self.assertTrue(r["authors"].endswith(" et al."))
        self.assertIn("Author 24", r["authors"])  # 25 shown (0..24), then et al.
        self.assertNotIn("Author 25", r["authors"])

    @patch.object(ArxivSource, "search", new=AsyncMock(return_value=[]))
    def test_second_search_rate_limited(self):
        self._search(title="foo")  # first: allowed
        resp = self._search(title="foo")  # within the source's cooldown
        self.assertEqual(resp.status_code, 429)

    @patch.object(ArxivSource, "search", new=AsyncMock(side_effect=RuntimeError("boom")))
    def test_source_failure_returns_500(self):
        resp = self._search(title="foo")
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.json())

    @patch.object(
        ArxivSource, "search", new=AsyncMock(side_effect=RuntimeError("HTTP 429 too many requests"))
    )
    def test_upstream_rate_limit_returns_429(self):
        resp = self._search(title="foo")
        self.assertEqual(resp.status_code, 429)
        self.assertIn("arXiv", resp.json()["error"])

    def test_search_requires_login(self):
        self.client.logout()
        resp = self._search(title="foo")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    @patch.object(ArxivSource, "search", new=AsyncMock(return_value=[]))
    def test_search_other_users_profile_404(self):
        other = PBUser.objects.create_user(email="o2@example.com", password="SecurePass123!")
        op = Profile.objects.create(user=other, name="OP", source_categories={"arxiv": ["cs.AI"]})
        resp = self.client.get(f"/profiles/{op.pk}/search/", {"title": "x"})
        self.assertEqual(resp.status_code, 404)
