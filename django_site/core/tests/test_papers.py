"""Tests for paper upload/dedup, deletion, and detail views."""

import tempfile
from pathlib import Path
from django.test import TestCase, override_settings
from core.models import Corpus, PBUser, Paper, Profile
from core.views import _compute_sha256


@override_settings(PAPER_STORAGE_DIR=Path(tempfile.mkdtemp()))
class PaperUploadDedupTests(TestCase):
    """Tests for paper upload deduplication via SHA-256."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="uploader@example.com", password="SecurePass123!",
        )
        self.profile = Profile.objects.create(
            user=self.user, name="Test Profile", categories=["cs.AI"],
        )
        self.client.login(username="uploader@example.com", password="SecurePass123!")

    def _make_pdf(self, content=b"%PDF-1.4 test content"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile("test.pdf", content, content_type="application/pdf")

    def test_upload_creates_paper_and_link(self):
        pdf = self._make_pdf()
        resp = self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": pdf},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Paper.objects.count(), 1)
        paper = Paper.objects.first()
        self.assertIsNotNone(paper.sha256)
        self.assertEqual(paper.sha256, _compute_sha256(b"%PDF-1.4 test content"))
        # Paper is linked to the profile's corpus
        self.assertEqual(paper.corpora.count(), 1)

    def test_duplicate_upload_reuses_paper(self):
        """Same file uploaded twice to same profile — one Paper, one link."""
        content = b"%PDF-1.4 duplicate test"
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(content)},
        )
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(content)},
        )
        self.assertEqual(Paper.objects.count(), 1)
        self.assertEqual(Paper.objects.first().corpora.count(), 1)  # not duplicated

    def test_same_paper_two_profiles_one_row(self):
        """Same file added to two profiles — one Paper row, two corpus links."""
        profile2 = Profile.objects.create(
            user=self.user, name="Second Profile", categories=["cs.LG"],
        )
        content = b"%PDF-1.4 shared paper"
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(content)},
        )
        self.client.post(
            f"/profiles/{profile2.pk}/upload/",
            {"files": self._make_pdf(content)},
        )
        self.assertEqual(Paper.objects.count(), 1)
        self.assertEqual(Paper.objects.first().corpora.count(), 2)  # two corpus links

    def test_different_papers_separate_rows(self):
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(b"%PDF-1.4 paper A")},
        )
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(b"%PDF-1.4 paper B")},
        )
        self.assertEqual(Paper.objects.count(), 2)

    def test_upload_stores_file_in_hash_path(self):
        content = b"%PDF-1.4 hash path test"
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": self._make_pdf(content)},
        )
        paper = Paper.objects.first()
        self.assertIn(paper.sha256[:2], paper.pdf_path)
        self.assertTrue(Path(paper.pdf_path).exists())

    def test_invalid_pdf_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        bad_file = SimpleUploadedFile("bad.pdf", b"not a pdf", content_type="application/pdf")
        self.client.post(
            f"/profiles/{self.profile.pk}/upload/",
            {"files": bad_file},
        )
        self.assertEqual(Paper.objects.count(), 0)


@override_settings(PAPER_STORAGE_DIR=Path(tempfile.mkdtemp()))
class PaperDeleteTests(TestCase):
    """Tests for paper removal (unlink from corpus, not file deletion)."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="deleter@example.com", password="SecurePass123!",
        )
        self.profile = Profile.objects.create(
            user=self.user, name="Del Profile", categories=["cs.AI"],
        )
        self.corpus = Corpus.objects.create(
            user=self.user,
            name=f"user_{self.user.pk}_profile_{self.profile.pk}",
        )
        self.paper = Paper.objects.create(
            title="Test Paper",
            sha256="a" * 64,
            source="user",
        )
        self.paper.corpora.add(self.corpus)
        self.client.login(username="deleter@example.com", password="SecurePass123!")

    def test_delete_removes_link_not_paper(self):
        resp = self.client.post(
            f"/profiles/{self.profile.pk}/papers/{self.paper.pk}/delete/"
        )
        self.assertEqual(resp.status_code, 302)
        # Link removed
        self.assertFalse(self.paper.corpora.filter(pk=self.corpus.pk).exists())
        # Paper row still exists
        self.assertTrue(Paper.objects.filter(pk=self.paper.pk).exists())

    def test_cannot_delete_other_users_paper(self):
        other = PBUser.objects.create_user(
            email="other@example.com", password="SecurePass123!",
        )
        other_profile = Profile.objects.create(
            user=other, name="Other", categories=["cs.AI"],
        )
        resp = self.client.post(
            f"/profiles/{other_profile.pk}/papers/{self.paper.pk}/delete/"
        )
        self.assertEqual(resp.status_code, 404)


@override_settings(PAPER_STORAGE_DIR=Path(tempfile.mkdtemp()))
class PaperViewTests(TestCase):
    """Tests for paper viewing (ownership check)."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="viewer@example.com", password="SecurePass123!",
        )
        self.profile = Profile.objects.create(
            user=self.user, name="View Profile", categories=["cs.AI"],
        )
        self.corpus = Corpus.objects.create(
            user=self.user,
            name=f"user_{self.user.pk}_profile_{self.profile.pk}",
        )
        # Create a paper with a real file on disk
        from django.conf import settings as django_settings
        sha = "b" * 64
        dest = django_settings.PAPER_STORAGE_DIR / sha[:2] / f"{sha}.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-1.4 view test")
        self.paper = Paper.objects.create(
            title="Viewable Paper", sha256=sha, pdf_path=str(dest), source="user",
        )
        self.paper.corpora.add(self.corpus)
        self.client.login(username="viewer@example.com", password="SecurePass123!")

    def test_view_linked_paper(self):
        resp = self.client.get(
            f"/profiles/{self.profile.pk}/papers/{self.paper.pk}/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_view_unlinked_paper_404(self):
        """Paper exists but not linked to this profile's corpus."""
        other_paper = Paper.objects.create(
            title="Unlinked", sha256="c" * 64, source="user",
        )
        resp = self.client.get(
            f"/profiles/{self.profile.pk}/papers/{other_paper.pk}/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_view_nonexistent_paper_404(self):
        resp = self.client.get(
            f"/profiles/{self.profile.pk}/papers/99999/"
        )
        self.assertEqual(resp.status_code, 404)
