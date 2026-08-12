"""Tests for profile create/read/update/delete."""

from django.test import TestCase
from core.models import PBUser, Profile


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
            "categories": "cs.AI,cs.LG",
        }
        data.update(overrides)
        return data

    # ── Create ────────────────────────────────────────────

    def test_create_profile(self):
        resp = self.client.post("/profiles/create/", self._valid_profile_data())
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Profile.objects.filter(user=self.user, name="AI Research").exists()
        )

    def test_create_profile_stores_categories(self):
        self.client.post("/profiles/create/", self._valid_profile_data())
        profile = Profile.objects.get(user=self.user, name="AI Research")
        self.assertEqual(profile.categories, ["cs.AI", "cs.LG"])

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
            user=self.other_user, name="Other", categories=["cs.AI"],
        )
        resp = self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_delete_other_users_profile(self):
        profile = Profile.objects.create(
            user=self.other_user, name="Other", categories=["cs.AI"],
        )
        resp = self.client.post(f"/profiles/{profile.pk}/delete/")
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Profile.objects.filter(pk=profile.pk).exists())
