"""Tests for _query_profile_recommendations and recommendations_view."""

import json
from datetime import date, datetime, timezone

from django.test import TestCase

from core.models import (
    Corpus, PBUser, Paper, Profile, Recommendation, RecommendationRun, Summary,
)
from core.views import _get_or_create_user_corpus, _query_profile_recommendations


def _make_paper(arxiv_id, title, submitted_date=None, categories=None, authors=None, abstract=""):
    """Create a Paper (sha256 left null; metadata drives categories/authors)."""
    return Paper.objects.create(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        submitted_date=submitted_date,
        metadata={"categories": categories or [], "authors": authors or []},
        source="arxiv",
    )


class _RecTestBase(TestCase):
    """Shared fixtures: a user, a reference corpus, and run/rec helpers."""

    def setUp(self):
        self.user = PBUser.objects.create_user(email="rec@example.com", password="SecurePass123!")
        # Every run needs a reference (arXiv) corpus; its name intentionally
        # does NOT match the user_<pk>_profile_<pk> pattern the query scans.
        self.ref = Corpus.objects.create(user=self.user, name="ref_arxiv")

    def _run_for(self, profile, total=10):
        corpus = _get_or_create_user_corpus(self.user, profile)
        return RecommendationRun.objects.create(
            user=self.user, user_corpus=corpus, ref_corpus=self.ref,
            profile=profile, total_papers_fetched=total,
        )

    def _rec(self, run, paper, score, rank=1):
        return Recommendation.objects.create(
            run=run, profile=run.profile, paper=paper, score=score, rank=rank,
        )


class QueryProfileRecommendationsTests(_RecTestBase):
    """_query_profile_recommendations: scoping, dedup, serialization, empties."""

    def test_single_profile_returns_only_that_profiles_recs(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        pb = Profile.objects.create(user=self.user, name="B", categories=["cs.LG"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "Paper A"), 0.8)
        self._rec(self._run_for(pb), _make_paper("2301.00002", "Paper B"), 0.7)
        aids = {r["arxiv_id"] for r in _query_profile_recommendations(self.user, pa)}
        self.assertEqual(aids, {"2301.00001"})

    def test_all_profiles_aggregates_across_corpora(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        pb = Profile.objects.create(user=self.user, name="B", categories=["cs.LG"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "Paper A"), 0.8)
        self._rec(self._run_for(pb), _make_paper("2301.00002", "Paper B"), 0.7)
        aids = {r["arxiv_id"] for r in _query_profile_recommendations(self.user, None)}
        self.assertEqual(aids, {"2301.00001", "2301.00002"})

    def test_dedup_keeps_highest_score_across_runs(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        d = datetime(2023, 6, 15, tzinfo=timezone.utc)
        # Two Paper rows sharing an arxiv_id, recommended in two different runs.
        self._rec(self._run_for(pa), _make_paper("2301.00001", "Low", submitted_date=d), 0.5)
        self._rec(self._run_for(pa), _make_paper("2301.00001", "High", submitted_date=d), 0.9)
        results = _query_profile_recommendations(self.user, pa)
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["score"], 0.9)
        self.assertEqual(results[0]["title"], "High")

    def test_paper_without_date_gets_unknown(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "No Date", submitted_date=None), 0.5)
        r = _query_profile_recommendations(self.user, pa)[0]
        self.assertIsNone(r["date_obj"])
        self.assertEqual(r["date_str"], "Unknown Date")

    def test_paper_with_date_is_formatted(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        dated = _make_paper("2301.00001", "Dated", submitted_date=datetime(2023, 6, 15, tzinfo=timezone.utc))
        self._rec(self._run_for(pa), dated, 0.5)
        r = _query_profile_recommendations(self.user, pa)[0]
        self.assertEqual(r["date_obj"], date(2023, 6, 15))
        self.assertEqual(r["date_str"], "15 June 2023")

    def test_summary_only_from_abstract_mode(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        run = self._run_for(pa)
        p1 = _make_paper("2301.00001", "Has Summary")
        p2 = _make_paper("2301.00002", "No Abstract Summary")
        Summary.objects.create(paper=p1, mode="abstract", summary_text="A concise summary.")
        # A 'full'-mode summary must NOT be used — only 'abstract'.
        Summary.objects.create(paper=p2, mode="full", summary_text="Full-text summary.")
        self._rec(run, p1, 0.8, rank=1)
        self._rec(run, p2, 0.7, rank=2)
        by_aid = {r["arxiv_id"]: r for r in _query_profile_recommendations(self.user, pa)}
        self.assertEqual(by_aid["2301.00001"]["summary_text"], "A concise summary.")
        self.assertEqual(by_aid["2301.00002"]["summary_text"], "")

    def test_profile_with_no_corpus_returns_empty(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        self.assertEqual(_query_profile_recommendations(self.user, pa), [])

    def test_corpus_with_no_runs_returns_empty(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        _get_or_create_user_corpus(self.user, pa)          # corpus exists, no runs
        self.assertEqual(_query_profile_recommendations(self.user, pa), [])

    def test_run_with_no_recommendations_returns_empty(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        self._run_for(pa)                                   # run exists, no recs
        self.assertEqual(_query_profile_recommendations(self.user, pa), [])

    def test_all_profiles_no_corpora_returns_empty(self):
        Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])  # no corpus
        self.assertEqual(_query_profile_recommendations(self.user, None), [])

    def test_user_isolation(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "Mine"), 0.8)
        # Another user with their own profile/run/recommendation.
        other = PBUser.objects.create_user(email="other@example.com", password="SecurePass123!")
        other_ref = Corpus.objects.create(user=other, name="ref_arxiv")
        other_p = Profile.objects.create(user=other, name="OB", categories=["cs.LG"])
        other_run = RecommendationRun.objects.create(
            user=other, user_corpus=_get_or_create_user_corpus(other, other_p),
            ref_corpus=other_ref, profile=other_p, total_papers_fetched=5,
        )
        Recommendation.objects.create(
            run=other_run, profile=other_p, paper=_make_paper("2301.99999", "Theirs"),
            score=0.9, rank=1,
        )
        aids = {r["arxiv_id"] for r in _query_profile_recommendations(self.user, None)}
        self.assertEqual(aids, {"2301.00001"})


class RecommendationsViewTests(_RecTestBase):
    """recommendations_view: recs_json / categories_json, empty states."""

    def setUp(self):
        super().setUp()
        self.client.login(username="rec@example.com", password="SecurePass123!")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get("/recommendations/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)

    def test_no_profiles_returns_empty_json(self):
        resp = self.client.get("/recommendations/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.context["recs_json"]), [])
        self.assertEqual(json.loads(resp.context["categories_json"]), [])

    def test_recs_json_has_expected_fields(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        paper = _make_paper(
            "2301.00001", "A Paper",
            submitted_date=datetime(2023, 6, 15, tzinfo=timezone.utc),
            categories=["cs.AI"], authors=["Jane Doe"], abstract="An abstract.",
        )
        Summary.objects.create(paper=paper, mode="abstract", summary_text="A summary.")
        self._rec(self._run_for(pa), paper, 0.85)
        recs = json.loads(self.client.get("/recommendations/").context["recs_json"])
        self.assertEqual(len(recs), 1)
        r = recs[0]
        for field in ("title", "score", "arxiv_id", "date_iso", "date_str",
                      "abstract", "summary_text", "categories"):
            self.assertIn(field, r)
        self.assertEqual(r["arxiv_id"], "2301.00001")
        self.assertAlmostEqual(r["score"], 0.85)
        self.assertEqual(r["date_iso"], "2023-06-15")
        self.assertEqual(r["date_str"], "15 June 2023")
        self.assertEqual(r["abstract"], "An abstract.")
        self.assertEqual(r["summary_text"], "A summary.")
        self.assertEqual(r["categories"], ["cs.AI"])
        self.assertNotIn("date_obj", r)                     # stripped during serialization

    def test_recs_json_null_date_serialization(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "No Date", submitted_date=None), 0.5)
        r = json.loads(self.client.get("/recommendations/").context["recs_json"])[0]
        self.assertIsNone(r["date_iso"])
        self.assertEqual(r["date_str"], "Unknown Date")

    def test_categories_json_unions_all_profiles(self):
        Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        Profile.objects.create(user=self.user, name="B", categories=["cs.LG", "math.CO"])
        cats = json.loads(self.client.get("/recommendations/").context["categories_json"])
        self.assertEqual(cats, ["cs.AI", "cs.LG", "math.CO"])

    def test_categories_json_scoped_to_selected_profile(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        Profile.objects.create(user=self.user, name="B", categories=["cs.LG", "math.CO"])
        cats = json.loads(
            self.client.get(f"/recommendations/?profile={pa.pk}").context["categories_json"]
        )
        self.assertEqual(cats, ["cs.AI"])

    def test_selected_profile_filters_recs(self):
        pa = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])
        pb = Profile.objects.create(user=self.user, name="B", categories=["cs.LG"])
        self._rec(self._run_for(pa), _make_paper("2301.00001", "A"), 0.8)
        self._rec(self._run_for(pb), _make_paper("2301.00002", "B"), 0.7)
        recs = json.loads(
            self.client.get(f"/recommendations/?profile={pa.pk}").context["recs_json"]
        )
        self.assertEqual({r["arxiv_id"] for r in recs}, {"2301.00001"})



class RecommendationAddToProfileTests(_RecTestBase):
    """recommendation_add_to_profile_view: link a recommended paper to a corpus."""

    def setUp(self):
        super().setUp()
        self.client.login(username="rec@example.com", password="SecurePass123!")
        self.profile = Profile.objects.create(user=self.user, name="A", categories=["cs.AI"])

    def _add(self, profile_id, paper_id):
        return self.client.post(
            f"/recommendations/add/{profile_id}/{paper_id}/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _recommend(self, paper):
        """Recommend `paper` to self.user so the view's was_recommended check passes."""
        return self._rec(self._run_for(self.profile), paper, 0.8)

    def test_add_recommended_paper_links_to_corpus(self):
        paper = _make_paper("2301.00001", "Rec Paper")
        self._recommend(paper)
        resp = self._add(self.profile.pk, paper.pk)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertFalse(data["already_linked"])
        self.assertEqual(data["paper"]["arxiv_id"], "2301.00001")
        corpus = _get_or_create_user_corpus(self.user, self.profile)
        self.assertTrue(paper.corpora.filter(pk=corpus.pk).exists())

    def test_add_already_linked_is_idempotent(self):
        paper = _make_paper("2301.00001", "Rec Paper")
        self._recommend(paper)
        paper.corpora.add(_get_or_create_user_corpus(self.user, self.profile))
        resp = self._add(self.profile.pk, paper.pk)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["already_linked"])

    def test_add_paper_not_recommended_to_user_404(self):
        # Paper recommended only to a different user -> not addable by this user.
        other = PBUser.objects.create_user(email="other@example.com", password="SecurePass123!")
        other_ref = Corpus.objects.create(user=other, name="ref_arxiv")
        other_p = Profile.objects.create(user=other, name="OB", categories=["cs.LG"])
        other_run = RecommendationRun.objects.create(
            user=other, user_corpus=_get_or_create_user_corpus(other, other_p),
            ref_corpus=other_ref, profile=other_p, total_papers_fetched=1,
        )
        paper = _make_paper("2301.00001", "Theirs")
        Recommendation.objects.create(run=other_run, profile=other_p, paper=paper, score=0.9, rank=1)
        resp = self._add(self.profile.pk, paper.pk)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.json()["ok"])

    def test_add_nonexistent_paper_404(self):
        resp = self._add(self.profile.pk, 999999)
        self.assertEqual(resp.status_code, 404)

    def test_add_other_users_profile_404(self):
        paper = _make_paper("2301.00001", "Rec Paper")
        self._recommend(paper)
        other = PBUser.objects.create_user(email="other2@example.com", password="SecurePass123!")
        other_p = Profile.objects.create(user=other, name="OP", categories=["cs.AI"])
        resp = self._add(other_p.pk, paper.pk)
        self.assertEqual(resp.status_code, 404)

    def test_add_requires_post(self):
        resp = self.client.get(f"/recommendations/add/{self.profile.pk}/1/")
        self.assertEqual(resp.status_code, 405)

    def test_add_requires_login(self):
        self.client.logout()
        paper = _make_paper("2301.00001", "Rec Paper")
        resp = self._add(self.profile.pk, paper.pk)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/auth/login/", resp.url)
