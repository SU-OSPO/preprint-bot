"""Tests for profile create/read/update/delete."""

import datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
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


class NextDigestDateTests(SimpleTestCase):
    """Weekly digests go out on Mondays, monthly on the 1st."""

    def _next(self, frequency, today):
        return Profile(frequency=frequency).next_digest_date(today=today)

    def test_daily_has_no_date(self):
        self.assertIsNone(self._next("daily", datetime.date(2026, 11, 18)))

    def test_weekly_midweek(self):
        # Wednesday -> following Monday
        self.assertEqual(
            self._next("weekly", datetime.date(2026, 11, 18)), datetime.date(2026, 11, 23)
        )

    def test_weekly_on_monday_is_next_week(self):
        self.assertEqual(
            self._next("weekly", datetime.date(2026, 11, 16)), datetime.date(2026, 11, 23)
        )

    def test_monthly_midmonth(self):
        self.assertEqual(
            self._next("monthly", datetime.date(2026, 11, 18)), datetime.date(2026, 12, 1)
        )

    def test_monthly_on_the_1st_is_next_month(self):
        self.assertEqual(
            self._next("monthly", datetime.date(2026, 11, 1)), datetime.date(2026, 12, 1)
        )

    def test_monthly_rolls_over_year(self):
        self.assertEqual(
            self._next("monthly", datetime.date(2026, 12, 31)), datetime.date(2027, 1, 1)
        )


class ProfileListNextDigestTests(TestCase):
    """The profile list shows when the next weekly/monthly digest is due."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="next@example.com",
            password="SecurePass123!",
        )
        self.client.login(username="next@example.com", password="SecurePass123!")

    def _create(self, **kwargs):
        return Profile.objects.create(
            user=self.user, source_categories={"arxiv": ["cs.AI"]}, **kwargs
        )

    def test_weekly_shows_next_date(self):
        profile = self._create(name="W", frequency="weekly")
        expected = profile.next_digest_date().strftime("%a, %b %-d")
        resp = self.client.get("/profiles/")
        self.assertContains(resp, f"(next on {expected})")

    def test_daily_shows_no_date(self):
        self._create(name="D", frequency="daily")
        resp = self.client.get("/profiles/")
        self.assertNotContains(resp, "next on")

    def test_paused_shows_no_date(self):
        self._create(name="P", frequency="monthly", email_notify=False)
        resp = self.client.get("/profiles/")
        self.assertNotContains(resp, "next on")

    def test_editor_explains_schedule(self):
        resp = self.client.get("/profiles/create/")
        self.assertContains(resp, "monthly digests on the 1st of each month")
        # Linked to the dropdown's aria-describedby for screen readers
        self.assertContains(resp, 'id="id_frequency_helptext"')


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

    def test_edit_keeps_selections_for_a_disabled_source(self):
        """Codes for a source the deployment no longer enables must survive.

        The picker can only render enabled sources, so those codes are absent
        from the submitted form; dropping them would silently delete data.
        """
        self.client.post("/profiles/create/", self._valid_profile_data())
        profile = Profile.objects.get(user=self.user)
        profile.source_categories = {"arxiv": ["cs.AI"], "demo": ["neuro"]}
        profile.save()

        resp = self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(categories="arxiv:cs.LG"),
        )
        self.assertEqual(resp.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(profile.source_categories, {"arxiv": ["cs.LG"], "demo": ["neuro"]})

    def test_edit_rerender_does_not_override_submitted_categories(self):
        """A failed POST must not reseed the picker from the stored profile.

        The bound form already holds what the user picked; handing the JS the
        persisted selection instead would overwrite their edits.
        """
        self.client.post("/profiles/create/", self._valid_profile_data())
        self.client.post("/profiles/create/", self._valid_profile_data(name="Other"))
        profile = Profile.objects.get(user=self.user, name="Other")

        # Renaming onto an existing name re-renders the bound form.
        resp = self.client.post(
            f"/profiles/{profile.pk}/edit/",
            self._valid_profile_data(name="AI Research", categories="arxiv:stat.ML"),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["initial_categories"], [])
        self.assertEqual(resp.context["form"]["categories"].value(), "arxiv:stat.ML")

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
