"""Tests for registration, login/logout, email verification, and password reset."""

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from core.models import PBUser


class AuthFlowTests(TestCase):
    """Tests for registration, login, logout, and access control."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="test@example.com",
            password="SecurePass123!",
            name="Test User",
        )

    # ── Registration ──────────────────────────────────────

    def test_register_creates_user(self):
        resp = self.client.post("/auth/register/", {
            "email": "new@example.com",
            "name": "New User",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        self.assertEqual(resp.status_code, 302)  # redirect to dashboard
        self.assertTrue(PBUser.objects.filter(email="new@example.com").exists())

    def test_register_logs_in_automatically(self):
        self.client.post("/auth/register/", {
            "email": "auto@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        resp = self.client.get("/")
        # New accounts enter onboarding on first login: still authenticated,
        # so redirected to /onboarding/ rather than bounced to /auth/login/.
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/onboarding/", resp.url)

    def test_register_duplicate_email_rejected(self):
        resp = self.client.post("/auth/register/", {
            "email": "test@example.com",
            "name": "",
            "password": "AnotherPass99!",
            "confirm_password": "AnotherPass99!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on register page
        self.assertEqual(PBUser.objects.filter(email="test@example.com").count(), 1)

    def test_register_case_insensitive_duplicate(self):
        resp = self.client.post("/auth/register/", {
            "email": "TEST@EXAMPLE.COM",
            "name": "",
            "password": "AnotherPass99!",
            "confirm_password": "AnotherPass99!",
        })
        self.assertEqual(resp.status_code, 200)  # rejected — already exists
        self.assertEqual(PBUser.objects.count(), 1)

    def test_register_password_mismatch(self):
        resp = self.client.post("/auth/register/", {
            "email": "mismatch@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "DifferentPassword99!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on register page
        self.assertFalse(PBUser.objects.filter(email="mismatch@example.com").exists())

    def test_register_weak_password_rejected(self):
        resp = self.client.post("/auth/register/", {
            "email": "weak@example.com",
            "name": "",
            "password": "123",
            "confirm_password": "123",
        })
        self.assertEqual(resp.status_code, 200)  # stays on register page
        self.assertFalse(PBUser.objects.filter(email="weak@example.com").exists())

    # ── Login ─────────────────────────────────────────────

    def test_login_valid_credentials(self):
        resp = self.client.post("/auth/login/", {
            "email": "test@example.com",
            "password": "SecurePass123!",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

    def test_login_case_insensitive_email(self):
        resp = self.client.post("/auth/login/", {
            "email": "TEST@Example.COM",
            "password": "SecurePass123!",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

    def test_login_wrong_password(self):
        resp = self.client.post("/auth/login/", {
            "email": "test@example.com",
            "password": "WrongPassword!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on login page

    def test_login_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.post("/auth/login/", {
            "email": "test@example.com",
            "password": "SecurePass123!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on login page

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username="test@example.com", password="SecurePass123!")
        resp = self.client.get("/auth/login/")
        self.assertEqual(resp.status_code, 302)  # redirected to dashboard

    # ── Logout ────────────────────────────────────────────

    def test_logout_requires_post(self):
        self.client.login(username="test@example.com", password="SecurePass123!")
        resp = self.client.get("/auth/logout/")
        self.assertEqual(resp.status_code, 405)  # method not allowed

    def test_logout_clears_session(self):
        self.client.login(username="test@example.com", password="SecurePass123!")
        self.client.post("/auth/logout/")
        resp = self.client.get("/profiles/")
        self.assertEqual(resp.status_code, 302)  # redirected to login
        self.assertIn("/auth/login/", resp.url)

    # ── Access control ────────────────────────────────────

    def test_unauthenticated_home_shows_landing(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)  # public landing page
        self.assertTemplateUsed(resp, "landing.html")

    def test_unauthenticated_redirected_to_login(self):
        resp = self.client.get("/profiles/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    def test_next_url_preserved(self):
        resp = self.client.get("/profiles/")
        self.assertIn("next=", resp.url)
        self.assertIn("%2Fprofiles%2F", resp.url)


class RegisterFormValidationTests(SimpleTestCase):
    """Additional form-level tests for RegisterForm."""

    def test_password_mismatch_error(self):
        from core.forms import RegisterForm
        form = RegisterForm(data={
            "email": "x@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "DifferentPassword99!",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("Passwords do not match", str(form.errors))

    def test_weak_password_error(self):
        from core.forms import RegisterForm
        form = RegisterForm(data={
            "email": "x@example.com",
            "name": "",
            "password": "abc",
            "confirm_password": "abc",
        })
        self.assertFalse(form.is_valid())


class EmailVerificationOffTests(TestCase):
    """When REQUIRE_EMAIL_VERIFICATION is False (default), registration
    should auto-login and login should not check email_verified."""

    def test_register_auto_logs_in(self):
        """Default behavior: register and immediately access dashboard."""
        self.client.post("/auth/register/", {
            "email": "new@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        resp = self.client.get("/")
        # New accounts enter onboarding on first login (still authenticated).
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/onboarding/", resp.url)

    def test_register_does_not_send_email(self):
        self.client.post("/auth/register/", {
            "email": "no-email@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        self.assertEqual(len(mail.outbox), 0)

    def test_login_allows_unverified_user(self):
        user = PBUser.objects.create_user(
            email="unverified@example.com", password="SecurePass123!",
        )
        self.assertFalse(user.email_verified)
        resp = self.client.post("/auth/login/", {
            "email": "unverified@example.com",
            "password": "SecurePass123!",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)


@override_settings(REQUIRE_EMAIL_VERIFICATION=True)
class EmailVerificationOnTests(TestCase):
    """When REQUIRE_EMAIL_VERIFICATION is True, registration should
    send a verification email and block login until verified."""

    # ── Registration ──────────────────────────────────────

    def test_register_sends_verification_email(self):
        resp = self.client.post("/auth/register/", {
            "email": "verify@example.com",
            "name": "Test",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        self.assertEqual(resp.status_code, 200)  # renders verify_email_sent
        self.assertContains(resp, "Check Your Email")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify@example.com", mail.outbox[0].to)
        self.assertIn("verify-email", mail.outbox[0].body)

    def test_register_does_not_auto_login(self):
        self.client.post("/auth/register/", {
            "email": "nologin@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        resp = self.client.get("/profiles/")
        self.assertEqual(resp.status_code, 302)  # redirected to login

    def test_register_creates_unverified_user(self):
        self.client.post("/auth/register/", {
            "email": "unverified@example.com",
            "name": "",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        user = PBUser.objects.get(email="unverified@example.com")
        self.assertFalse(user.email_verified)

    # ── Login blocked ─────────────────────────────────────

    def test_login_blocked_for_unverified_user(self):
        PBUser.objects.create_user(
            email="blocked@example.com", password="SecurePass123!",
        )
        resp = self.client.post("/auth/login/", {
            "email": "blocked@example.com",
            "password": "SecurePass123!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on login
        self.assertContains(resp, "verify your email")
        self.assertContains(resp, "resend-verification")

    def test_login_works_for_verified_user(self):
        user = PBUser.objects.create_user(
            email="verified@example.com", password="SecurePass123!",
        )
        user.email_verified = True
        user.save()
        resp = self.client.post("/auth/login/", {
            "email": "verified@example.com",
            "password": "SecurePass123!",
        })
        self.assertRedirects(resp, "/", fetch_redirect_response=False)

    # ── Verification link ─────────────────────────────────

    def test_verify_email_link_works(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        user = PBUser.objects.create_user(
            email="link@example.com", password="SecurePass123!",
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        resp = self.client.get(f"/auth/verify-email/{uid}/{token}/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_verify_email_invalid_token_rejected(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        user = PBUser.objects.create_user(
            email="bad@example.com", password="SecurePass123!",
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        resp = self.client.get(f"/auth/verify-email/{uid}/bad-token/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)

        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    # ── Resend ────────────────────────────────────────────

    def test_resend_verification(self):
        PBUser.objects.create_user(
            email="resend@example.com", password="SecurePass123!",
        )
        # Trigger login to set session key
        self.client.post("/auth/login/", {
            "email": "resend@example.com",
            "password": "SecurePass123!",
        })
        resp = self.client.get("/auth/resend-verification/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Check Your Email")
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_without_session_redirects(self):
        resp = self.client.get("/auth/resend-verification/")
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)


class PasswordResetFlowTests(TestCase):
    """Forgot-password (email issuance, no user enumeration) and reset."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="reset@example.com", password="OldPass123!",
        )

    def _reset_url(self, user):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return f"/auth/reset-password/{uid}/{token}/"

    def test_forgot_password_sends_email_for_existing_user(self):
        resp = self.client.post("/auth/forgot-password/", {"email": "reset@example.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_forgot_password_silent_for_unknown_email(self):
        resp = self.client.post("/auth/forgot-password/", {"email": "nobody@example.com"})
        self.assertEqual(resp.status_code, 200)  # same response — no user enumeration
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_with_valid_token_changes_password(self):
        resp = self.client.post(self._reset_url(self.user), {
            "new_password": "BrandNewPass99!",
            "confirm_password": "BrandNewPass99!",
        })
        self.assertRedirects(resp, "/auth/login/", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass99!"))

    def test_reset_with_invalid_token_redirects(self):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = self.client.get(f"/auth/reset-password/{uid}/bad-token/")
        self.assertRedirects(resp, "/auth/forgot-password/", fetch_redirect_response=False)

    def test_reset_password_mismatch_rejected(self):
        resp = self.client.post(self._reset_url(self.user), {
            "new_password": "BrandNewPass99!",
            "confirm_password": "Different99!",
        })
        self.assertEqual(resp.status_code, 200)  # stays on the form
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("BrandNewPass99!"))
