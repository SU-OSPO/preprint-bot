"""Tests for ORCID sign-in, account completion, and link/unlink."""

from unittest.mock import patch
from django.test import TestCase, override_settings
from core.models import PBUser


@override_settings(ORCID_CLIENT_ID="", ORCID_CLIENT_SECRET="")
class OrcidDisabledTests(TestCase):
    """With ORCID unconfigured, ORCID features are hidden."""

    def test_login_page_has_no_orcid_button(self):
        resp = self.client.get("/auth/login/")
        self.assertNotContains(resp, "orcid")

    def test_orcid_login_redirects_with_error(self):
        resp = self.client.get("/auth/orcid/login/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    def test_orcid_callback_redirects_with_error(self):
        resp = self.client.get("/auth/orcid/callback/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)


@override_settings(ORCID_CLIENT_ID="APP-TEST123", ORCID_CLIENT_SECRET="test-secret")
class OrcidLoginTests(TestCase):
    """ORCID login redirect and callback handling."""

    def test_login_page_shows_orcid_button(self):
        resp = self.client.get("/auth/login/")
        self.assertContains(resp, "Sign in with ORCID")
        self.assertContains(resp, "/auth/orcid/login/")

    def test_register_page_shows_orcid_button(self):
        resp = self.client.get("/auth/register/")
        self.assertContains(resp, "Sign up with ORCID")

    def test_orcid_login_redirects_to_orcid(self):
        resp = self.client.get("/auth/orcid/login/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("orcid.org/oauth/authorize", resp.url)
        self.assertIn("APP-TEST123", resp.url)

    def test_orcid_login_sets_state_in_session(self):
        self.client.get("/auth/orcid/login/")
        self.assertIn("orcid_oauth_state", self.client.session)

    def test_callback_state_mismatch_rejected(self):
        # Set a state in session
        session = self.client.session
        session["orcid_oauth_state"] = "correct-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {"state": "wrong-state", "code": "abc"})
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    def test_callback_error_param_handled(self):
        session = self.client.session
        session["orcid_oauth_state"] = "some-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "some-state", "error": "access_denied",
        })
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    @patch("core.orcid.exchange_code")
    def test_callback_existing_user_logs_in(self, mock_exchange):
        """Existing user with orcid_id is logged in directly."""
        mock_exchange.return_value = {
            "orcid": "0000-0001-2345-6789",
            "name": "Test Researcher",
            "access_token": "fake-token",
        }
        user = PBUser.objects.create_user(
            email="orcid-user@example.com",
            password="SecurePass123!",
            orcid_id="0000-0001-2345-6789",
        )

        session = self.client.session
        session["orcid_oauth_state"] = "valid-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "valid-state", "code": "auth-code-123",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

        # Verify user is logged in (first login → onboarding redirect, not login)
        dash = self.client.get("/")
        self.assertEqual(dash.status_code, 302)
        self.assertIn("/onboarding/", dash.url)

    @patch("core.orcid.fetch_email", return_value="fromorcid@example.com")
    @patch("core.orcid.exchange_code")
    def test_callback_new_user_with_email_creates_account(self, mock_exchange, mock_email):
        """New user whose email is available from ORCID — account created directly."""
        mock_exchange.return_value = {
            "orcid": "0000-0002-1111-2222",
            "name": "Auto Researcher",
            "access_token": "fake-token",
        }

        session = self.client.session
        session["orcid_oauth_state"] = "valid-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "valid-state", "code": "auth-code-auto",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

        user = PBUser.objects.get(orcid_id="0000-0002-1111-2222")
        self.assertEqual(user.email, "fromorcid@example.com")
        self.assertTrue(user.email_verified)

    @patch("core.orcid.fetch_email", return_value="taken@example.com")
    @patch("core.orcid.exchange_code")
    def test_callback_new_user_email_taken_redirects_to_complete(self, mock_exchange, mock_email):
        """ORCID email already in use — fall through to completion form."""
        PBUser.objects.create_user(email="taken@example.com", password="Pass123!")
        mock_exchange.return_value = {
            "orcid": "0000-0002-3333-4444",
            "name": "Collision Researcher",
            "access_token": "fake-token",
        }

        session = self.client.session
        session["orcid_oauth_state"] = "valid-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "valid-state", "code": "auth-code-collision",
        })
        self.assertRedirects(resp, "/auth/orcid/complete/", fetch_redirect_response=False)

    @patch("core.orcid.fetch_email", return_value=None)
    @patch("core.orcid.exchange_code")
    def test_callback_new_user_no_email_redirects_to_complete(self, mock_exchange, mock_email):
        """New ORCID user with no public email is sent to the completion form."""
        mock_exchange.return_value = {
            "orcid": "0000-0002-3456-7890",
            "name": "New Researcher",
            "access_token": "fake-token",
        }

        session = self.client.session
        session["orcid_oauth_state"] = "valid-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "valid-state", "code": "auth-code-456",
        })
        self.assertRedirects(resp, "/auth/orcid/complete/", fetch_redirect_response=False)

        # Session should have pending ORCID data
        self.assertEqual(
            self.client.session["orcid_pending"]["orcid_id"],
            "0000-0002-3456-7890",
        )

    @patch("core.orcid.exchange_code")
    def test_callback_failed_exchange_shows_error(self, mock_exchange):
        mock_exchange.return_value = None

        session = self.client.session
        session["orcid_oauth_state"] = "valid-state"
        session.save()

        resp = self.client.get("/auth/orcid/callback/", {
            "state": "valid-state", "code": "bad-code",
        })
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)


@override_settings(ORCID_CLIENT_ID="APP-TEST123", ORCID_CLIENT_SECRET="test-secret")
class OrcidCompleteTests(TestCase):
    """ORCID account completion (email collection for new users)."""

    def setUp(self):
        # Simulate a pending ORCID sign-in
        session = self.client.session
        session["orcid_pending"] = {
            "orcid_id": "0000-0003-4567-8901",
            "name": "New Researcher",
        }
        session.save()

    def test_complete_page_renders(self):
        resp = self.client.get("/auth/orcid/complete/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "0000-0003-4567-8901")
        self.assertContains(resp, "New Researcher")

    def test_complete_creates_user(self):
        resp = self.client.post("/auth/orcid/complete/", {
            "email": "researcher@example.com",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

        user = PBUser.objects.get(email="researcher@example.com")
        self.assertEqual(user.orcid_id, "0000-0003-4567-8901")
        self.assertEqual(user.name, "New Researcher")
        self.assertTrue(user.email_verified)

    def test_complete_logs_in_user(self):
        self.client.post("/auth/orcid/complete/", {"email": "auto@example.com"})
        resp = self.client.get("/")
        # New accounts enter onboarding on first login (still authenticated).
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/onboarding/", resp.url)

    def test_complete_duplicate_email_rejected(self):
        PBUser.objects.create_user(email="taken@example.com", password="Pass123!")
        resp = self.client.post("/auth/orcid/complete/", {"email": "taken@example.com"})
        self.assertEqual(resp.status_code, 200)  # stays on form
        self.assertFalse(PBUser.objects.filter(orcid_id="0000-0003-4567-8901").exists())

    def test_complete_without_session_redirects(self):
        # Clear the pending session data
        session = self.client.session
        if "orcid_pending" in session:
            del session["orcid_pending"]
        session.save()

        resp = self.client.get("/auth/orcid/complete/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    def test_complete_clears_session(self):
        self.client.post("/auth/orcid/complete/", {"email": "clear@example.com"})
        self.assertNotIn("orcid_pending", self.client.session)


@override_settings(ORCID_CLIENT_ID="APP-TEST123", ORCID_CLIENT_SECRET="test-secret")
class OrcidLinkTests(TestCase):
    """Linking an ORCID iD to an existing, logged-in account."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="linker@example.com", password="SecurePass123!",
        )
        self.client.login(username="linker@example.com", password="SecurePass123!")

    def test_link_requires_login(self):
        self.client.logout()
        resp = self.client.get("/auth/orcid/link/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    def test_link_redirects_to_orcid_and_sets_link_mode(self):
        resp = self.client.get("/auth/orcid/link/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("orcid.org/oauth/authorize", resp.url)
        self.assertTrue(self.client.session.get("orcid_link_mode"))
        self.assertIn("orcid_oauth_state", self.client.session)

    def test_link_when_already_linked_redirects_to_settings(self):
        self.user.orcid_id = "0000-0001-0000-0001"
        self.user.save(update_fields=["orcid_id"])
        resp = self.client.get("/auth/orcid/link/")
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)

    @patch("core.orcid.exchange_code")
    def test_link_callback_attaches_orcid(self, mock_exchange):
        mock_exchange.return_value = {
            "orcid": "0000-0001-2222-3333", "name": "L", "access_token": "t",
        }
        session = self.client.session
        session["orcid_oauth_state"] = "st"
        session["orcid_link_mode"] = True
        session.save()
        resp = self.client.get("/auth/orcid/callback/", {"state": "st", "code": "c"})
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.orcid_id, "0000-0001-2222-3333")

    @patch("core.orcid.exchange_code")
    def test_link_callback_duplicate_orcid_rejected(self, mock_exchange):
        PBUser.objects.create_user(
            email="owner@example.com", password="SecurePass123!",
            orcid_id="0000-0001-9999-9999",
        )
        mock_exchange.return_value = {
            "orcid": "0000-0001-9999-9999", "name": "Dup", "access_token": "t",
        }
        session = self.client.session
        session["orcid_oauth_state"] = "st"
        session["orcid_link_mode"] = True
        session.save()
        resp = self.client.get("/auth/orcid/callback/", {"state": "st", "code": "c"})
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.orcid_id)  # not linked to the taken iD


class OrcidUnlinkTests(TestCase):
    """Unlinking a previously linked ORCID iD."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="unlinker@example.com", password="SecurePass123!",
            orcid_id="0000-0002-8888-7777",
        )
        self.client.login(username="unlinker@example.com", password="SecurePass123!")

    def test_unlink_removes_orcid(self):
        resp = self.client.post("/auth/orcid/unlink/")
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.orcid_id)

    def test_unlink_when_none_is_noop(self):
        self.user.orcid_id = None
        self.user.save(update_fields=["orcid_id"])
        resp = self.client.post("/auth/orcid/unlink/")
        self.assertRedirects(resp, "/settings/", fetch_redirect_response=False)

    def test_unlink_requires_post(self):
        resp = self.client.get("/auth/orcid/unlink/")
        self.assertEqual(resp.status_code, 405)

    def test_unlink_requires_login(self):
        self.client.logout()
        resp = self.client.post("/auth/orcid/unlink/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)
