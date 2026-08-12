"""Tests for settings/account management: profile settings, email toggles, deactivation, deletion."""

from django.test import TestCase
from core.models import PBUser, Profile


class SettingsViewTests(TestCase):
    """Settings page: load, profile/email update, ownership of email change."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="settings@example.com", password="SecurePass123!", name="Orig Name",
        )
        self.client.login(username="settings@example.com", password="SecurePass123!")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get("/settings/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    def test_page_loads(self):
        resp = self.client.get("/settings/")
        self.assertEqual(resp.status_code, 200)

    def test_update_name_and_email(self):
        resp = self.client.post("/settings/", {"name": "New Name", "email": "moved@example.com"})
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "New Name")
        self.assertEqual(self.user.email, "moved@example.com")

    def test_email_change_to_taken_is_rejected(self):
        PBUser.objects.create_user(email="taken@example.com", password="SecurePass123!")
        self.client.post("/settings/", {"name": "X", "email": "taken@example.com"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "settings@example.com")  # unchanged


class EmailToggleTests(TestCase):
    """Per-profile email toggle and bulk pause/resume."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="toggle@example.com", password="SecurePass123!",
        )
        self.p1 = Profile.objects.create(
            user=self.user, name="P1", categories=["cs.AI"], email_notify=True,
        )
        self.p2 = Profile.objects.create(
            user=self.user, name="P2", categories=["cs.LG"], email_notify=True,
        )
        self.client.login(username="toggle@example.com", password="SecurePass123!")

    def test_toggle_profile_email_pauses_then_resumes(self):
        self.client.post(f"/settings/toggle-email/{self.p1.pk}/")
        self.p1.refresh_from_db()
        self.assertFalse(self.p1.email_notify)
        self.client.post(f"/settings/toggle-email/{self.p1.pk}/")
        self.p1.refresh_from_db()
        self.assertTrue(self.p1.email_notify)

    def test_toggle_requires_post(self):
        resp = self.client.get(f"/settings/toggle-email/{self.p1.pk}/")
        self.assertEqual(resp.status_code, 405)

    def test_toggle_other_users_profile_404(self):
        other = PBUser.objects.create_user(email="o@example.com", password="SecurePass123!")
        op = Profile.objects.create(user=other, name="OP", categories=["cs.AI"])
        resp = self.client.post(f"/settings/toggle-email/{op.pk}/")
        self.assertEqual(resp.status_code, 404)

    def test_pause_all_emails(self):
        resp = self.client.post("/settings/pause-all-emails/", {"action": "pause"})
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.assertEqual(Profile.objects.filter(user=self.user, email_notify=True).count(), 0)

    def test_resume_all_emails(self):
        Profile.objects.filter(user=self.user).update(email_notify=False)
        self.client.post("/settings/pause-all-emails/", {"action": "resume"})
        self.assertEqual(Profile.objects.filter(user=self.user, email_notify=False).count(), 0)

    def test_pause_all_requires_login(self):
        self.client.logout()
        resp = self.client.post("/settings/pause-all-emails/", {"action": "pause"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)


class AccountDeactivationTests(TestCase):
    """Deactivation: sets is_active=False, pauses emails, logs out."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="deact@example.com", password="SecurePass123!",
        )
        self.profile = Profile.objects.create(
            user=self.user, name="P", categories=["cs.AI"], email_notify=True,
        )
        self.client.login(username="deact@example.com", password="SecurePass123!")

    def test_deactivate_sets_inactive_and_logs_out(self):
        resp = self.client.post("/settings/deactivate/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        # Logged out: a protected page now bounces to login.
        follow = self.client.get("/settings/")
        self.assertEqual(follow.status_code, 302)
        self.assertIn("/auth/login/", follow.url)

    def test_deactivate_pauses_all_emails(self):
        self.client.post("/settings/deactivate/")
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.email_notify)

    def test_deactivate_requires_post(self):
        resp = self.client.get("/settings/deactivate/")
        self.assertEqual(resp.status_code, 405)

    def test_deactivate_requires_login(self):
        self.client.logout()
        resp = self.client.post("/settings/deactivate/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)


class AccountDeletionTests(TestCase):
    """Deletion: requires typed confirmation, cascades, logs out."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="del@example.com", password="SecurePass123!",
        )
        self.profile = Profile.objects.create(
            user=self.user, name="P", categories=["cs.AI"],
        )
        self.client.login(username="del@example.com", password="SecurePass123!")

    def test_wrong_confirmation_does_not_delete(self):
        resp = self.client.post("/settings/delete-account/", {"confirmation": "nope"})
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.assertTrue(PBUser.objects.filter(pk=self.user.pk).exists())

    def test_missing_confirmation_does_not_delete(self):
        self.client.post("/settings/delete-account/", {})
        self.assertTrue(PBUser.objects.filter(pk=self.user.pk).exists())

    def test_delete_with_confirmation(self):
        resp = self.client.post("/settings/delete-account/", {"confirmation": "DELETE"})
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)
        self.assertFalse(PBUser.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Profile.objects.filter(pk=self.profile.pk).exists())  # cascade

    def test_delete_requires_post(self):
        resp = self.client.get("/settings/delete-account/")
        self.assertEqual(resp.status_code, 405)

    def test_delete_requires_login(self):
        self.client.logout()
        resp = self.client.post("/settings/delete-account/", {"confirmation": "DELETE"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)
