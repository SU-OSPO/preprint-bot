"""Tests for copying papers between a user's own profiles (#145)."""

from django.test import TestCase

from core.models import PBUser, Paper, Profile
from core.views import _get_or_create_user_corpus


class SearchExistingPapersTests(TestCase):
    """GET /profiles/<id>/search-existing/: search papers in the user's profiles."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="copy@example.com")
        self.client.force_login(self.user)
        self.source_profile = Profile.objects.create(user=self.user, name="Source")
        self.target_profile = Profile.objects.create(user=self.user, name="Target")
        self.source_corpus = _get_or_create_user_corpus(self.user, self.source_profile)

    def _search_existing(self, q):
        return self.client.get(f"/profiles/{self.target_profile.pk}/search-existing/", {"q": q})

    def test_search_returns_matching_paper_from_another_profile(self):
        matching = Paper.objects.create(title="Graph neural networks")
        unrelated = Paper.objects.create(title="Ocean currents")
        matching.corpora.add(self.source_corpus)
        unrelated.corpora.add(self.source_corpus)

        response = self._search_existing("network")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()["results"]], [matching.pk])

    def test_paper_in_two_profiles_appears_once(self):
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
