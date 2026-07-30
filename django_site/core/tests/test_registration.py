"""Tests for REGISTRATION_OPEN gating of registration and ORCID new accounts."""

from unittest.mock import patch
from django.test import TestCase, override_settings
from core.models import PBUser


@override_settings(REGISTRATION_OPEN=False)
class RegistrationClosedTests(TestCase):
    """Password registration and the 'Create account' link are gated off."""

    def test_register_get_redirects_to_login(self):
        resp = self.client.get("/auth/register/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    def test_register_post_blocked(self):
        resp = self.client.post("/auth/register/", {
            "email": "blocked@example.com", "name": "",
            "password": "GoodPassword99!", "confirm_password": "GoodPassword99!",
        })
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)
        self.assertFalse(PBUser.objects.filter(email="blocked@example.com").exists())

    def test_login_page_hides_create_account(self):
        resp = self.client.get("/auth/login/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "/auth/register/")

    def test_landing_page_hides_create_account(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "/auth/register/")


@override_settings(REGISTRATION_OPEN=True)
class RegistrationOpenLinkVisibleTests(TestCase):
    """Sanity check the other side of the gate: default REGISTRATION_OPEN
    (True) shows the register link."""

    def test_login_page_shows_create_account(self):
        resp = self.client.get("/auth/login/")
        self.assertContains(resp, "/auth/register/")


@override_settings(
    REGISTRATION_OPEN=False,
    ORCID_CLIENT_ID="APP-TEST123", ORCID_CLIENT_SECRET="test-secret",
)
class RegistrationClosedOrcidTests(TestCase):
    """Closed registration also blocks ORCID new-account creation, but still
    lets an existing ORCID user sign in."""

    @patch("core.orcid.fetch_email", return_value="new-orcid@example.com")
    @patch("core.orcid.exchange_code")
    def test_orcid_new_account_blocked(self, mock_exchange, mock_email):
        mock_exchange.return_value = {
            "orcid": "0000-0003-1111-2222", "name": "New", "access_token": "t",
        }
        session = self.client.session
        session["orcid_oauth_state"] = "st"
        session.save()
        resp = self.client.get("/auth/orcid/callback/", {"state": "st", "code": "c"})
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)
        self.assertFalse(PBUser.objects.filter(orcid_id="0000-0003-1111-2222").exists())

    def test_orcid_complete_blocked(self):
        session = self.client.session
        session["orcid_pending"] = {"orcid_id": "0000-0003-4444-5555", "name": "X"}
        session.save()
        resp = self.client.get("/auth/orcid/complete/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

    @patch("core.orcid.exchange_code")
    def test_existing_orcid_user_still_signs_in(self, mock_exchange):
        PBUser.objects.create_user(
            email="existing@example.com", password="SecurePass123!",
            orcid_id="0000-0003-6666-7777",
        )
        mock_exchange.return_value = {
            "orcid": "0000-0003-6666-7777", "name": "E", "access_token": "t",
        }
        session = self.client.session
        session["orcid_oauth_state"] = "st"
        session.save()
        resp = self.client.get("/auth/orcid/callback/", {"state": "st", "code": "c"})
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/auth/login/", resp.url)  # signed in, not blocked
