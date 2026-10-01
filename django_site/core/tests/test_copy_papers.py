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

    def test_search_returns_matching_paper_from_another_profile(self):
        matching = Paper.objects.create(title="Graph neural networks")
        unrelated = Paper.objects.create(title="Ocean currents")
        matching.corpora.add(self.source_corpus)
        unrelated.corpora.add(self.source_corpus)

        response = self.client.get(
            f"/profiles/{self.target_profile.pk}/search-existing/", {"q": "network"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()["results"]], [matching.pk])
