"""Tests for profile create/read/update/delete."""

from unittest.mock import patch

from django.test import TestCase
from core.models import PBUser, Profile


class ProfileListSourceLabelTests(TestCase):
    """Category source names follow the enabled-source count, not usage."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="labels@example.com",
            password="SecurePass123!",
        )
        self.client.login(username="labels@example.com", password="SecurePass123!")
        Profile.objects.create(
            user=self.user,
            name="A",
            source_categories={"arxiv": ["cs.AI"]},
        )

    def test_hidden_with_a_single_enabled_source(self):
        resp = self.client.get("/profiles/")
        self.assertFalse(resp.context["show_source_labels"])

    def test_shown_with_several_enabled_even_if_profile_uses_one(self):
        """The profile only tracks arXiv, but a bare code is still ambiguous."""
        with patch("core.sources.enabled_names", return_value=["arxiv", "biorxiv"]):
            resp = self.client.get("/profiles/")
        self.assertTrue(resp.context["show_source_labels"])


class ProfileCRUDTests(TestCase):
    """Tests for profile create, edit, delete, and ownership."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="owner@example.com",
            password="SecurePass123!",
        )
        self.other_user = PBUser.objects.create_user(
            email="other@example.com",
            password="SecurePass123!",
        )
        self.client.login(username="owner@example.com", password="SecurePass123!")

    def _valid_profile_data(self, **overrides):
        data = {
            "name": "AI Research",
            "frequency": "weekly",
            "threshold": "0.6",
            "top_x": "25",
            "categories": "arxiv:cs.AI,arxiv:cs.LG",
        }
        data.update(overrides)
        return data

    # ── Create ────────────────────────────────────────────

    def test_create_profile(self):
        resp = self.client.post("/profiles/create/", self._valid_profile_data())
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Profile.objects.filter(user=self.user, name="AI Research").exists())

    def test_create_profile_stores_categories(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        profile = Profile.objects.get(user=self.user, name="AI Research")
        self.assertEqual(profile.source_categories, {"arxiv": ["cs.AI", "cs.LG"]})

    def test_create_profile_stores_threshold(self):
        self.client.post(
            "/profiles/create/",
            self._valid_profile_data(threshold="0.45"),
        )
        profile = Profile.objects.get(user=self.user)
        self.assertAlmostEqual(profile.threshold, 0.45)

    def test_create_duplicate_name_rejected(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        resp = self.client.post("/profiles/create/", self._valid_profile_data())
        self.assertEqual(resp.status_code, 200)  # stays on form
        self.assertEqual(
            Profile.objects.filter(user=self.user, name__iexact="AI Research").count(),
            1,
        )

    def test_create_duplicate_name_case_insensitive(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        resp = self.client.post(
            "/profiles/create/",
            self._valid_profile_data(name="ai research"),
        )
        self.assertEqual(resp.status_code, 200)  # rejected
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)

    def test_create_missing_categories_rejected(self):
        resp = self.client.post(
            "/profiles/create/",
            self._valid_profile_data(categories=""),
        )
        self.assertEqual(resp.status_code, 200)  # stays on form
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 0)

    # ── Edit ──────────────────────────────────────────────

    def test_edit_profile(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        profile = Profile.objects.get(user=self.user)
        resp = self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(name="Renamed"),
        )
        self.assertEqual(resp.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.name, "Renamed")

    def test_edit_preserves_other_fields(self):
        self.client.post(
            "/profiles/create/",
            self._valid_profile_data(top_x="50"),
        )
        profile = Profile.objects.get(user=self.user)
        self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(name="Updated", top_x="100"),
        )
        profile.refresh_from_db()
        self.assertEqual(profile.top_x, 100)

    # ── Delete ────────────────────────────────────────────

    def test_delete_profile(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        profile = Profile.objects.get(user=self.user)
        resp = self.client.post(f"/profiles/{profile.pk}/delete/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Profile.objects.filter(pk=profile.pk).exists())

    # ── Ownership ─────────────────────────────────────────

    def test_cannot_edit_other_users_profile(self):
        profile = Profile.objects.create(
            user=self.other_user,
            name="Other",
            source_categories={"arxiv": ["cs.AI"]},
        )
        resp = self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_delete_other_users_profile(self):
        profile = Profile.objects.create(
            user=self.other_user,
            name="Other",
            source_categories={"arxiv": ["cs.AI"]},
        )
        resp = self.client.post(f"/profiles/{profile.pk}/delete/")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Profile.objects.filter(pk=profile.pk).exists())
