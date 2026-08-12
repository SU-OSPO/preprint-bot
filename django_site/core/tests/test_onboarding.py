"""Tests for the onboarding flow and returning-user navigation."""

from django.test import TestCase
from core.models import Corpus, PBUser, Paper, Profile


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
