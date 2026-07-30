"""
Tier 1 tests — pure functions and form validation.

Run with:
    python manage.py test core
"""

from pathlib import Path

from django.test import SimpleTestCase

from core.views import _parse_arxiv_ids, _compute_sha256


# ── _parse_arxiv_ids ──────────────────────────────────────────────────────


class ParseArxivIdsTests(SimpleTestCase):
    """Tests for _parse_arxiv_ids(), which extracts valid arXiv IDs
    from free-form user input."""

    # ── Basic bare IDs ────────────────────────────────────

    def test_bare_new_format(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345"), ["2301.12345"])

    def test_bare_new_format_four_digits(self):
        self.assertEqual(_parse_arxiv_ids("2301.1234"), ["2301.1234"])

    def test_bare_new_format_five_digits(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345"), ["2301.12345"])

    def test_bare_new_format_six_digits_invalid(self):
        self.assertEqual(_parse_arxiv_ids("2301.123456"), [])  # 6 digits — invalid

    def test_bare_legacy_format(self):
        self.assertEqual(_parse_arxiv_ids("hep-th/9901001"), ["hep-th/9901001"])

    def test_bare_legacy_with_subcategory(self):
        self.assertEqual(_parse_arxiv_ids("math.GT/0309136"), ["math.GT/0309136"])

    # ── Prefix stripping ──────────────────────────────────

    def test_abs_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018"),
            ["2601.19018"],
        )

    def test_pdf_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018"),
            ["2601.19018"],
        )

    def test_arxiv_colon_prefix(self):
        self.assertEqual(_parse_arxiv_ids("arXiv:2601.19018"), ["2601.19018"])

    def test_arxiv_colon_case_insensitive(self):
        self.assertEqual(_parse_arxiv_ids("ARXIV:2301.12345"), ["2301.12345"])

    # ── Version suffix stripping ──────────────────────────

    def test_version_suffix(self):
        self.assertEqual(_parse_arxiv_ids("2601.19018v1"), ["2601.19018"])

    def test_version_suffix_high(self):
        self.assertEqual(_parse_arxiv_ids("2601.19018v12"), ["2601.19018"])

    def test_url_with_version(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018v3"),
            ["2601.19018"],
        )

    # ── .pdf suffix stripping ─────────────────────────────

    def test_pdf_extension(self):
        """Versioned PDF URL — the bug that was fixed."""
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018v2.pdf"),
            ["2601.19018"],
        )

    def test_pdf_extension_no_version(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2301.12345.pdf"),
            ["2301.12345"],
        )

    def test_pdf_extension_case_insensitive(self):
        self.assertEqual(_parse_arxiv_ids("2301.12345.PDF"), ["2301.12345"])

    # ── Query strings / fragments ─────────────────────────

    def test_query_string(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/2601.19018v2.pdf?download"),
            ["2601.19018"],
        )

    def test_fragment(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2601.19018#section1"),
            ["2601.19018"],
        )

    # ── Legacy IDs via URL ────────────────────────────────

    def test_legacy_id_abs_url(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/hep-th/9901001"),
            ["hep-th/9901001"],
        )

    def test_legacy_id_pdf_url_versioned(self):
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/pdf/hep-th/9901001v2.pdf?download"),
            ["hep-th/9901001"],
        )

    # ── Multiple IDs ──────────────────────────────────────

    def test_comma_separated(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345, 2302.67890"),
            ["2301.12345", "2302.67890"],
        )

    def test_newline_separated(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345\n2302.67890"),
            ["2301.12345", "2302.67890"],
        )

    def test_mixed_formats(self):
        result = _parse_arxiv_ids(
            "https://arxiv.org/abs/2601.19018, arXiv:2301.12345, 2302.67890"
        )
        self.assertEqual(result, ["2601.19018", "2301.12345", "2302.67890"])

    # ── Deduplication ─────────────────────────────────────

    def test_deduplication(self):
        self.assertEqual(
            _parse_arxiv_ids("2301.12345, 2301.12345"),
            ["2301.12345"],
        )

    def test_dedup_across_formats(self):
        """Same ID via URL and bare — should appear once."""
        self.assertEqual(
            _parse_arxiv_ids("https://arxiv.org/abs/2301.12345, 2301.12345"),
            ["2301.12345"],
        )

    # ── Invalid input ─────────────────────────────────────

    def test_empty_string(self):
        self.assertEqual(_parse_arxiv_ids(""), [])

    def test_whitespace_only(self):
        self.assertEqual(_parse_arxiv_ids("   \n  \n  "), [])

    def test_garbage(self):
        self.assertEqual(_parse_arxiv_ids("not-an-id, hello world"), [])

    def test_partial_match_ignored(self):
        """Things that look almost like IDs but aren't."""
        self.assertEqual(_parse_arxiv_ids("12345"), [])
        self.assertEqual(_parse_arxiv_ids("2301.1"), [])


# ── Paper storage helpers ─────────────────────────────────────────────────


class PaperStorageTests(SimpleTestCase):
    """Tests for SHA-256 hashing and hash-based file storage."""

    def test_sha256_bytes(self):
        result = _compute_sha256(b"hello world")
        self.assertEqual(len(result), 64)  # hex-encoded SHA-256
        # Known hash of "hello world"
        self.assertEqual(
            result,
            "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9",
        )

    def test_sha256_deterministic(self):
        data = b"%PDF-1.4 test content"
        self.assertEqual(_compute_sha256(data), _compute_sha256(data))

    def test_sha256_different_content(self):
        self.assertNotEqual(
            _compute_sha256(b"paper version 1"),
            _compute_sha256(b"paper version 2"),
        )

    def test_paper_storage_path_format(self):
        from core.views import _paper_storage_path
        path = _paper_storage_path("a3f7b2c9e8d1" + "0" * 52)
        self.assertIn("a3", str(path))  # first two chars as subdirectory
        self.assertTrue(str(path).endswith(".pdf"))


# ── ProfileForm.clean_categories ──────────────────────────────────────────


class CleanCategoriesTests(SimpleTestCase):
    """Tests for ProfileForm category validation."""

    def _make_form(self, categories_str):
        """Build a ProfileForm with the given categories string and
        all other fields set to valid defaults."""
        from core.forms import ProfileForm
        return ProfileForm(data={
            "name": "Test Profile",
            "frequency": "weekly",
            "threshold": "0.6",
            "top_x": "10",
            "categories": categories_str,
        })

    # ── Valid categories ──────────────────────────────────

    def test_single_valid(self):
        form = self._make_form("cs.AI")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["categories"], ["cs.AI"])

    def test_multiple_valid(self):
        form = self._make_form("cs.AI,cs.LG,stat.ML")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            form.cleaned_data["categories"],
            ["cs.AI", "cs.LG", "stat.ML"],
        )

    def test_whitespace_trimmed(self):
        form = self._make_form("  cs.AI , cs.LG  ")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["categories"], ["cs.AI", "cs.LG"])

    def test_physics_hyphenated(self):
        """Categories like hep-th and gr-qc are valid."""
        form = self._make_form("hep-th,gr-qc,quant-ph")
        self.assertTrue(form.is_valid(), form.errors)

    def test_physics_dotted(self):
        form = self._make_form("physics.optics,cond-mat.stat-mech")
        self.assertTrue(form.is_valid(), form.errors)

    # ── Invalid categories ────────────────────────────────

    def test_empty_rejected(self):
        form = self._make_form("")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_whitespace_only_rejected(self):
        form = self._make_form("  ,  ,  ")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_unknown_code_rejected(self):
        form = self._make_form("cs.AI,not.real")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)
        self.assertIn("not.real", form.errors["categories"][0])

    def test_parent_group_rejected(self):
        """Parent codes like 'cs' are not leaf categories."""
        form = self._make_form("cs")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_completely_bogus_code_rejected(self):
        form = self._make_form("fake.CATEGORY")
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)

    def test_script_injection_rejected(self):
        """XSS attempt should fail validation."""
        form = self._make_form('cs.AI,</script><script>alert(1)</script>')
        self.assertFalse(form.is_valid())
        self.assertIn("categories", form.errors)


# ══════════════════════════════════════════════════════════════════════════
# Tier 2 tests — auth flows, profile CRUD, form validation (need DB)
# ══════════════════════════════════════════════════════════════════════════

from django.test import TestCase

from core.models import PBUser, Profile


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


# ══════════════════════════════════════════════════════════════════════════
# Email verification tests
# ══════════════════════════════════════════════════════════════════════════

from django.core import mail
from django.test import override_settings


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


# ══════════════════════════════════════════════════════════════════════════
# ORCID OAuth2 tests
# ══════════════════════════════════════════════════════════════════════════

from unittest.mock import patch


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


# ════════════════════════════════════════════════════════════════════════
# Paper deduplication tests
# ════════════════════════════════════════════════════════════════════════

import tempfile

from core.models import Corpus, Paper


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



# ══════════════════════════════════════════════════════════════════════════
# Onboarding flow — first-login walkthrough (gate, skip, finish)
# ══════════════════════════════════════════════════════════════════════════


class OnboardingTests(TestCase):
    """First-login onboarding: registering a new account authenticates via
    login_pbuser, which flags the session for onboarding (last_login was None).
    These tests exercise the gate, skip, finish, and no-retrigger behavior."""

    def setUp(self):
        # Registering auto-logs-in under the default (no email verification),
        # setting the onboarding session flag.
        self.client.post("/auth/register/", {
            "email": "newbie@example.com",
            "name": "Newbie",
            "password": "GoodPassword99!",
            "confirm_password": "GoodPassword99!",
        })
        self.user = PBUser.objects.get(email="newbie@example.com")

    def _add_paper(self, profile):
        """Link a paper to the profile's corpus, as the finish check expects."""
        corpus = Corpus.objects.create(
            user=self.user,
            name=f"user_{self.user.pk}_profile_{profile.pk}",
        )
        paper = Paper.objects.create(title="Seed Paper", sha256="b" * 64, source="user")
        paper.corpora.add(corpus)
        return paper

    # ── Gate ──────────────────────────────────────────────

    def test_first_login_redirects_to_onboarding(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/onboarding/profile/")

    def test_gate_resumes_at_papers_when_profile_exists(self):
        profile = Profile.objects.create(user=self.user, name="P1", categories=["cs.AI"])
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f"/onboarding/papers/{profile.pk}/")

    def test_onboarding_pages_are_reachable_while_gated(self):
        # The onboarding step itself is exempt from the gate (no bounce loop).
        resp = self.client.get("/onboarding/profile/")
        self.assertEqual(resp.status_code, 200)

    # ── Skip ──────────────────────────────────────────────

    def test_skip_ends_onboarding(self):
        resp = self.client.post("/onboarding/skip/")
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        # Flag cleared: the dashboard now loads normally.
        self.assertEqual(self.client.get("/").status_code, 200)

    # ── Finish ────────────────────────────────────────────

    def test_finish_requires_at_least_one_paper(self):
        profile = Profile.objects.create(user=self.user, name="P1", categories=["cs.AI"])
        resp = self.client.post("/onboarding/finish/", {"profile_id": profile.pk})
        # No papers → bounced back to the papers step, onboarding still active.
        self.assertRedirects(
            resp, f"/onboarding/papers/{profile.pk}/", fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_finish_with_paper_ends_onboarding(self):
        profile = Profile.objects.create(user=self.user, name="P1", categories=["cs.AI"])
        self._add_paper(profile)
        resp = self.client.post("/onboarding/finish/", {"profile_id": profile.pk})
        self.assertRedirects(resp, "/", fetch_redirect_response=False)
        # Onboarding done: the dashboard loads normally.
        self.assertEqual(self.client.get("/").status_code, 200)

    # ── No re-trigger ─────────────────────────────────────

    def test_no_retrigger_on_second_login(self):
        self.client.post("/auth/logout/")
        # last_login was set on the first login, so a second login won't re-flag.
        self.client.post("/auth/login/", {
            "email": "newbie@example.com",
            "password": "GoodPassword99!",
        })
        self.assertEqual(self.client.get("/").status_code, 200)


class ReturningUserNavigationTests(TestCase):
    """A logged-in user with no onboarding flag (client.login bypasses
    login_pbuser) reaches normal pages without an onboarding redirect."""

    def setUp(self):
        self.user = PBUser.objects.create_user(
            email="returning@example.com", password="SecurePass123!",
        )
        self.client.login(username="returning@example.com", password="SecurePass123!")

    def test_dashboard_loads_without_onboarding_redirect(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_profiles_page_loads(self):
        resp = self.client.get("/profiles/")
        self.assertEqual(resp.status_code, 200)
