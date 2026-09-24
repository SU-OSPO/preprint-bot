# test_pipeline_fetch.py
"""Unit tests for fetch_preprint_papers over enabled sources."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))

from preprint_bot.pipeline import fetch_preprint_papers  # noqa: E402
from preprint_sources import PaperEntry  # noqa: E402


def _entry(source, source_id):
    return PaperEntry(
        source_id=source_id,
        title=f"{source} {source_id}",
        abstract="",
        url="",
        pdf_url="",
        authors=[],
        categories=[],
        published="",
        source=source,
    )


def _source(name, label, latest=None, by_date=None):
    """A stand-in PreprintSource with just the attributes the fetch uses."""
    src = AsyncMock()
    # name/label are plain attributes, not coroutines.
    src.configure_mock(name=name, label=label)
    src.fetch_latest = latest if latest is not None else AsyncMock(return_value=[])
    src.fetch_by_date = by_date if by_date is not None else AsyncMock(return_value=[])
    return src


def _patch_registry(sources):
    """Patch the registry as pipeline.py imported it."""
    names = [s.name for s in sources]
    return (
        patch("preprint_bot.pipeline.enabled_sources", return_value=sources),
        patch("preprint_bot.pipeline.enabled_names", return_value=names),
    )


class TestFanOut:
    @pytest.mark.asyncio
    async def test_merges_entries_from_every_selected_source(self):
        a = _source("arxiv", "arXiv", AsyncMock(return_value=[_entry("arxiv", "1")]))
        b = _source(
            "biorxiv",
            "bioRxiv",
            AsyncMock(return_value=[_entry("biorxiv", "2"), _entry("biorxiv", "3")]),
        )
        p1, p2 = _patch_registry([a, b])
        with p1, p2:
            entries = await fetch_preprint_papers({"arxiv": ["cs.AI"], "biorxiv": ["neuro"]})

        assert [(e.source, e.source_id) for e in entries] == [
            ("arxiv", "1"),
            ("biorxiv", "2"),
            ("biorxiv", "3"),
        ]
        a.fetch_latest.assert_awaited_once_with(["cs.AI"])
        b.fetch_latest.assert_awaited_once_with(["neuro"])

    @pytest.mark.asyncio
    async def test_source_without_selected_categories_is_not_fetched(self):
        a = _source("arxiv", "arXiv", AsyncMock(return_value=[_entry("arxiv", "1")]))
        b = _source("biorxiv", "bioRxiv")
        p1, p2 = _patch_registry([a, b])
        with p1, p2:
            entries = await fetch_preprint_papers({"arxiv": ["cs.AI"], "biorxiv": []})

        assert len(entries) == 1
        b.fetch_latest.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_selections_for_a_disabled_source_are_ignored(self, capsys):
        """Profiles keep those codes on purpose; there is just nothing to fetch."""
        a = _source("arxiv", "arXiv", AsyncMock(return_value=[]))
        p1, p2 = _patch_registry([a])
        with p1, p2:
            await fetch_preprint_papers({"arxiv": ["cs.AI"], "osf": ["psych"]})

        assert "disabled source(s): osf" in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_nothing_selected_fetches_nothing(self):
        a = _source("arxiv", "arXiv")
        p1, p2 = _patch_registry([a])
        with p1, p2:
            assert await fetch_preprint_papers({}) == []
        a.fetch_latest.assert_not_awaited()


class TestFailureIsolation:
    @pytest.mark.asyncio
    async def test_one_failing_source_does_not_lose_the_others(self, capsys):
        a = _source("arxiv", "arXiv", AsyncMock(side_effect=RuntimeError("boom")))
        b = _source("biorxiv", "bioRxiv", AsyncMock(return_value=[_entry("biorxiv", "2")]))
        p1, p2 = _patch_registry([a, b])
        with p1, p2:
            entries = await fetch_preprint_papers({"arxiv": ["cs.AI"], "biorxiv": ["neuro"]})

        assert [e.source_id for e in entries] == ["2"]
        out = capsys.readouterr().out
        assert "arXiv: FAILED" in out
        assert "continuing without 1 failed source(s)" in out

    @pytest.mark.asyncio
    async def test_all_sources_failing_raises(self):
        """A wholly broken run must not be mistaken for a quiet day."""
        a = _source("arxiv", "arXiv", AsyncMock(side_effect=RuntimeError("boom")))
        b = _source("biorxiv", "bioRxiv", AsyncMock(side_effect=RuntimeError("bang")))
        p1, p2 = _patch_registry([a, b])
        with p1, p2, pytest.raises(RuntimeError, match="every preprint source failed"):
            await fetch_preprint_papers({"arxiv": ["cs.AI"], "biorxiv": ["neuro"]})


class TestHistoricalFetch:
    @pytest.mark.asyncio
    async def test_by_date_uses_fetch_by_date(self):
        from datetime import datetime

        when = datetime(2026, 1, 2)
        a = _source("arxiv", "arXiv", by_date=AsyncMock(return_value=[_entry("arxiv", "1")]))
        p1, p2 = _patch_registry([a])
        with p1, p2:
            entries = await fetch_preprint_papers({"arxiv": ["cs.AI"]}, target_date=when)

        assert len(entries) == 1
        a.fetch_by_date.assert_awaited_once_with(when, ["cs.AI"])
        a.fetch_latest.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_source_without_historical_support_is_skipped_not_fatal(self, capsys):
        from datetime import datetime

        a = _source("arxiv", "arXiv", by_date=AsyncMock(return_value=[_entry("arxiv", "1")]))
        b = _source("demo", "Demo Server", by_date=AsyncMock(side_effect=NotImplementedError))
        p1, p2 = _patch_registry([a, b])
        with p1, p2:
            entries = await fetch_preprint_papers(
                {"arxiv": ["cs.AI"], "demo": ["neuro"]}, target_date=datetime(2026, 1, 2)
            )

        assert [e.source_id for e in entries] == ["1"]
        assert "no historical fetch support" in capsys.readouterr().out
