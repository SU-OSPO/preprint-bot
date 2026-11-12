# test_pdf_retry.py
"""Tests for retrying rejected PDF downloads, within a run and in later runs."""

from email.utils import format_datetime
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from preprint_bot import download_arxiv_pdfs as dl
from preprint_bot import pipeline


def _response(status, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.content = b"%PDF-1.4"
    return r


PDF_OK = _response(200, {"Content-Type": "application/pdf"})


def _papers(n):
    return [
        {"source_id": f"10.1/{i}", "source": "biorxiv", "pdf_url": f"https://x/{i}.pdf"}
        for i in range(n)
    ]


def _run(tmp_path, responses, papers=None, **kwargs):
    """Download *papers* against a queue of responses; return (stats, get, backoffs)."""
    get = MagicMock(side_effect=list(responses))
    with patch.object(dl.requests, "get", get), patch.object(dl.time, "sleep") as sleep:
        stats = dl.download_arxiv_pdfs(
            papers or _papers(1), output_folder=str(tmp_path), min_delay=0, **kwargs
        )
    # min_delay=0 sleeps are the per-request delay; the rest are backoffs.
    backoffs = [c.args[0] for c in sleep.call_args_list if c.args[0] != 0]
    return stats, get, backoffs


class TestRetryAfter:
    def test_seconds(self):
        assert dl._retry_after_seconds(_response(429, {"Retry-After": "30"})) == 30

    def test_http_date(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=60)
        secs = dl._retry_after_seconds(_response(429, {"Retry-After": format_datetime(when)}))
        assert 55 <= secs <= 60

    def test_missing_or_unparseable(self):
        assert dl._retry_after_seconds(_response(429)) is None
        assert dl._retry_after_seconds(_response(429, {"Retry-After": "soon"})) is None


class TestDownloadRetries:
    def test_recovers_after_a_rejection(self, tmp_path):
        stats, get, backoffs = _run(tmp_path, [_response(403), PDF_OK])
        assert stats["downloaded"] == 1 and get.call_count == 2
        assert 5 <= backoffs[0] <= 5.5

    def test_backs_off_exponentially_with_jitter(self, tmp_path):
        stats, get, backoffs = _run(tmp_path, [_response(429)] * 5)
        assert stats["failed"] == 1 and get.call_count == 5
        for wait, base in zip(backoffs, [5, 10, 20, 40]):
            assert base <= wait <= base * 1.1
        assert len(backoffs) == 4

    def test_waits_at_least_retry_after(self, tmp_path):
        _, _, backoffs = _run(tmp_path, [_response(503, {"Retry-After": "30"}), PDF_OK])
        assert 30 <= backoffs[0] <= 33

    def test_gives_up_when_retry_after_exceeds_cap(self, tmp_path):
        stats, get, backoffs = _run(
            tmp_path, [_response(429, {"Retry-After": "3600"})], max_backoff=120
        )
        assert stats["failed"] == 1 and get.call_count == 1 and backoffs == []

    def test_does_not_retry_other_statuses(self, tmp_path):
        stats, get, _ = _run(tmp_path, [_response(404)])
        assert stats["failed"] == 1 and get.call_count == 1

    def test_stops_backing_off_after_consecutive_failures(self, tmp_path):
        # Two papers exhaust their 2 tries; the third and fourth get one each.
        responses = [_response(403)] * 6
        stats, get, _ = _run(
            tmp_path, responses, papers=_papers(4), max_retries=2, max_consecutive_failures=2
        )
        assert stats["failed"] == 4 and get.call_count == 6

    def test_success_resets_the_failure_streak(self, tmp_path):
        responses = [_response(403)] * 2 + [PDF_OK] + [_response(403)] * 4
        stats, get, _ = _run(
            tmp_path, responses, papers=_papers(3), max_retries=2, max_consecutive_failures=2
        )
        # Paper 1 fails (2 tries), paper 2 succeeds, paper 3 still gets 2 tries.
        assert stats["downloaded"] == 1 and get.call_count == 5


def _row(pid, source_id="10.1/a"):
    return {
        "id": pid,
        "source_id": source_id,
        "source": "biorxiv",
        "metadata": {"pdf_url": f"https://x/{pid}.pdf", "arxiv_url": ""},
    }


class TestRecoverMissingFulltext:
    @pytest.mark.asyncio
    async def test_retries_recent_papers_not_fetched_this_run(self):
        api = AsyncMock()
        api.get_papers_missing_sections.return_value = [_row(1), _row(2, "10.1/b")]
        with (
            patch.object(pipeline, "download_arxiv_pdfs") as download,
            patch.object(pipeline, "_parse_papers", AsyncMock(return_value={2})) as parse,
        ):
            recovered = await pipeline.recover_missing_fulltext(api, 7, exclude_ids={1})

        api.get_papers_missing_sections.assert_awaited_once_with(7, pipeline.FULLTEXT_RETRY_DAYS)
        specs = download.call_args.args[0]
        assert [s["pdf_url"] for s in specs] == ["https://x/2.pdf"]
        assert [p["id"] for p in parse.call_args.args[1]] == [2]
        assert recovered == {2}

    @pytest.mark.asyncio
    async def test_nothing_to_retry(self):
        api = AsyncMock()
        api.get_papers_missing_sections.return_value = []
        with patch.object(pipeline, "download_arxiv_pdfs") as download:
            assert await pipeline.recover_missing_fulltext(api, 7, exclude_ids=set()) == set()
        download.assert_not_called()


class TestRematch:
    def _corpora(self):
        return [
            {"corpus_id": 10, "user_id": 3, "profile": {"id": 5, "name": "p", "threshold": 0.6}}
        ]

    async def _candidates(self, api, rematch_ids):
        api.get_recommendations_by_run.return_value = []
        with patch.object(pipeline, "run_similarity_matching", AsyncMock(return_value=1)) as match:
            await pipeline.generate_recommendations(
                api, 1, self._corpora(), datetime(2026, 11, 12), {100}, rematch_ids=rematch_ids
            )
        return match.call_args.kwargs["paper_ids"]

    @pytest.mark.asyncio
    async def test_skips_papers_already_recommended_to_the_profile(self):
        api = AsyncMock()
        api.get_recommended_paper_ids.return_value = {201}
        assert await self._candidates(api, {200, 201}) == {100, 200}
        api.get_recommended_paper_ids.assert_awaited_once_with(5, {200, 201})

    @pytest.mark.asyncio
    async def test_lookup_failure_matches_only_this_runs_papers(self):
        api = AsyncMock()
        api.get_recommended_paper_ids.side_effect = RuntimeError("down")
        assert await self._candidates(api, {200}) == {100}

    @pytest.mark.asyncio
    async def test_no_rematch_ids_skips_the_lookup(self):
        api = AsyncMock()
        assert await self._candidates(api, set()) == {100}
        api.get_recommended_paper_ids.assert_not_called()
