"""Tests for copying papers between a user's own profiles."""

from django.test import TestCase

from core.models import PBUser, Paper, Profile
from core.views import _get_or_create_user_corpus


class SearchExistingPapersTests(TestCase):
    """paper_search_existing_api_view: scope, dedup, blank query, already-added flag."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="copy@example.com")
        self.client.force_login(self.user)
        self.source_profile = Profile.objects.create(user=self.user, name="Source")
        self.target_profile = Profile.objects.create(user=self.user, name="Target")
        self.source_corpus = _get_or_create_user_corpus(self.user, self.source_profile)

    def _search_existing(self, title):
        return self.client.get(
            f"/profiles/{self.target_profile.pk}/search-existing/", {"title": title}
        )

    def test_search_returns_matching_paper_from_another_profile(self):
        matching = Paper.objects.create(title="Graph neural networks")
        unrelated = Paper.objects.create(title="Ocean currents")
        matching.corpora.add(self.source_corpus)
        unrelated.corpora.add(self.source_corpus)

        response = self._search_existing("network")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()["results"]], [matching.pk])

    def test_paper_in_two_profiles_appears_once(self):
        """Linked to two of the user's profiles — returned once, not once per link."""
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        paper.corpora.add(_get_or_create_user_corpus(self.user, self.target_profile))

        response = self._search_existing("network")

        self.assertEqual([p["id"] for p in response.json()["results"]], [paper.pk])

    def test_paper_from_deleted_profile_is_not_found(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        self.source_profile.delete()

        response = self._search_existing("network")

        self.assertEqual([p["id"] for p in response.json()["results"]], [])

    def test_blank_query_returns_400(self):
        response = self._search_existing("")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_paper_already_added_in_this_profile_is_flagged(self):
        in_both = Paper.objects.create(title="Graph neural networks")
        in_both.corpora.add(self.source_corpus)
        in_both.corpora.add(_get_or_create_user_corpus(self.user, self.target_profile))

        only_in_source = Paper.objects.create(title="Neural network pruning")
        only_in_source.corpora.add(self.source_corpus)

        results = self._search_existing("network").json()["results"]
        flags = {r["id"]: r["already_added"] for r in results}
        self.assertEqual(flags, {in_both.pk: True, only_in_source.pk: False})

    def test_other_users_papers_are_not_found(self):
        mine = Paper.objects.create(title="Graph neural networks")
        mine.corpora.add(self.source_corpus)

        other_user = PBUser.objects.create_user(email="other@example.com")
        other_profile = Profile.objects.create(user=other_user, name="Theirs")
        theirs = Paper.objects.create(title="Neural network pruning")
        theirs.corpora.add(_get_or_create_user_corpus(other_user, other_profile))

        response = self._search_existing("network")

        self.assertEqual([p["id"] for p in response.json()["results"]], [mine.pk])

    def test_search_requires_login(self):
        self.client.logout()
        response = self._search_existing("network")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.url)

    def test_search_other_users_profile_404(self):
        other = PBUser.objects.create_user(email="o2@example.com")
        op = Profile.objects.create(user=other, name="OP")
        response = self.client.get(f"/profiles/{op.pk}/search-existing/", {"title": "x"})
        self.assertEqual(response.status_code, 404)


class CopyTabRenderingTests(TestCase):
    """The copy tab renders on the profiles page but not during onboarding."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="copy@example.com")
        self.client.force_login(self.user)
        self.profile = Profile.objects.create(user=self.user, name="Mine")

    def test_profiles_page_shows_copy_tab_with_search_url(self):
        response = self.client.get("/profiles/")

        self.assertContains(response, f'data-tab="existing-{self.profile.pk}"')
        self.assertContains(response, f"/profiles/{self.profile.pk}/search-existing/")

    def test_onboarding_page_hides_copy_tab(self):
        response = self.client.get(f"/onboarding/papers/{self.profile.pk}/")

        self.assertNotContains(response, f'data-tab="existing-{self.profile.pk}"')

    def test_copy_tab_carries_add_url(self):
        response = self.client.get("/profiles/")

        self.assertContains(response, f"/profiles/{self.profile.pk}/add-existing/0/")


class AddExistingPaperTests(TestCase):
    """paper_add_existing_view: link one of the user's papers into another profile."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="copy@example.com")
        self.client.force_login(self.user)
        self.source_profile = Profile.objects.create(user=self.user, name="Source")
        self.target_profile = Profile.objects.create(user=self.user, name="Target")
        self.source_corpus = _get_or_create_user_corpus(self.user, self.source_profile)
        self.target_corpus = _get_or_create_user_corpus(self.user, self.target_profile)

    def _add_existing(self, paper_id):
        return self.client.post(f"/profiles/{self.target_profile.pk}/add-existing/{paper_id}/")

    def test_add_links_paper_to_target_profile(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)

        response = self._add_existing(paper.pk)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["added"])
        self.assertEqual(response.json()["paper"]["id"], paper.pk)
        self.assertTrue(paper.corpora.filter(pk=self.target_corpus.pk).exists())
        # Copy, not move: the source profile keeps the paper.
        self.assertTrue(paper.corpora.filter(pk=self.source_corpus.pk).exists())

    def test_other_users_paper_404(self):
        other = PBUser.objects.create_user(email="other@example.com")
        other_profile = Profile.objects.create(user=other, name="Theirs")
        theirs = Paper.objects.create(title="Their private upload")
        theirs.corpora.add(_get_or_create_user_corpus(other, other_profile))

        response = self._add_existing(theirs.pk)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(theirs.corpora.filter(pk=self.target_corpus.pk).exists())

    def test_paper_only_in_deleted_profile_404(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        self.source_profile.delete()

        response = self._add_existing(paper.pk)

        self.assertEqual(response.status_code, 404)

    def test_add_to_other_users_profile_404(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        other = PBUser.objects.create_user(email="o2@example.com")
        op = Profile.objects.create(user=other, name="OP")

        response = self.client.post(f"/profiles/{op.pk}/add-existing/{paper.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_add_requires_login(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        self.client.logout()

        response = self._add_existing(paper.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.url)

    def test_add_requires_post(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)

        response = self.client.get(f"/profiles/{self.target_profile.pk}/add-existing/{paper.pk}/")

        self.assertEqual(response.status_code, 405)
        self.assertFalse(paper.corpora.filter(pk=self.target_corpus.pk).exists())

    def test_paper_already_in_target_is_not_added_again(self):
        paper = Paper.objects.create(title="Graph neural networks")
        paper.corpora.add(self.source_corpus)
        paper.corpora.add(self.target_corpus)

        response = self._add_existing(paper.pk)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(response.json()["added"])
        self.assertEqual(response.json()["paper"]["id"], paper.pk)
