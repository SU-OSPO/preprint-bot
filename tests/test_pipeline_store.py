# test_pipeline_store.py
"""Unit tests for store_fetched_papers: only unprocessed papers are worked on."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "preprint_bot"))

from preprint_bot.pipeline import store_fetched_papers  # noqa: E402
from preprint_sources import PaperEntry  # noqa: E402


def _entry(source_id):
    return PaperEntry(
        source_id=source_id,
        title=source_id,
        abstract="",
        url="",
        pdf_url=f"https://arxiv.org/pdf/{source_id}.pdf",
        authors=[],
        categories=[],
        published="",
        source="arxiv",
    )


def _api(existing, sections):
    """API client stub: *existing* maps source_id -> id; *sections* maps id -> rows."""
    api = AsyncMock()
    api.get_or_create_user.return_value = {"id": 1, "email": "system@example.com"}
    api.get_or_create_corpus.return_value = {"id": 7, "name": "arxiv_papers"}
    api.get_paper_by_source_id.side_effect = lambda sid, src: (
        {"id": existing[sid]} if sid in existing else None
    )
    api.get_sections_by_paper.side_effect = lambda pid: sections.get(pid, [])
    new_ids = iter(range(100, 200))
    api.create_paper.side_effect = lambda **kw: {"id": next(new_ids)}
    return api


async def _store(api, entries):
    with (
        patch("preprint_bot.pipeline.download_arxiv_pdfs", return_value={}) as dl,
        patch("preprint_bot.pipeline._parse_and_store_sections", new_callable=AsyncMock) as parse,
    ):
        result = await store_fetched_papers(api, entries)
    return result, dl, parse


class TestOnlyUnprocessedPapers:
    @pytest.mark.asyncio
    async def test_existing_parsed_papers_are_not_redone(self):
        api = _api(existing={"old": 1}, sections={1: [{"id": 9}]})
        (_, paper_ids, pending_ids, stored), dl, parse = await _store(
            api, [_entry("old"), _entry("new")]
        )
        assert paper_ids == {1, 100}
        assert pending_ids == {100}
        assert stored == 1
        assert [p["source_id"] for p in dl.call_args.args[0]] == ["new"]
        assert [e.source_id for e in parse.call_args.args[2]] == ["new"]

    @pytest.mark.asyncio
    async def test_stored_but_unparsed_paper_is_resumed(self):
        # An earlier run stored "old" and stopped before parsing it.
        api = _api(existing={"old": 1}, sections={})
        (_, _, pending_ids, stored), dl, parse = await _store(api, [_entry("old")])
        assert pending_ids == {1}
        assert stored == 0
        assert [p["source_id"] for p in dl.call_args.args[0]] == ["old"]
        assert [e.source_id for e in parse.call_args.args[2]] == ["old"]

    @pytest.mark.asyncio
    async def test_nothing_to_do_when_all_papers_processed(self):
        api = _api(existing={"a": 1, "b": 2}, sections={1: [{"id": 9}], 2: [{"id": 8}]})
        (_, paper_ids, pending_ids, _), dl, parse = await _store(api, [_entry("a"), _entry("b")])
        assert paper_ids == {1, 2}
        assert pending_ids == set()
        dl.assert_not_called()
        parse.assert_not_called()


class TestResumedParseFindsPdf:
    @pytest.mark.asyncio
    async def test_legacy_pdf_path_falls_back_to_current_name(self, tmp_path):
        # Row stored before filenames carried the source; its old file is gone
        # and the resumed download wrote the current name instead.
        from preprint_bot.pipeline import _parse_and_store_sections

        (tmp_path / "arxiv_2401.00001.pdf").write_bytes(b"%PDF")
        api = AsyncMock()
        api.get_papers_by_corpus.return_value = [
            {
                "id": 1,
                "source": "arxiv",
                "source_id": "2401.00001",
                "pdf_path": str(tmp_path / "2401.00001.pdf"),
            }
        ]
        with (
            patch("preprint_bot.pipeline.PDF_DIR", tmp_path),
            patch(
                "preprint_bot.pipeline.extract_grobid_sections",
                return_value={"sections": [{"header": "Intro", "text": "x"}]},
            ) as grobid,
        ):
            await _parse_and_store_sections(api, 7, [_entry("2401.00001")])
        assert grobid.call_args.args[0] == tmp_path / "arxiv_2401.00001.pdf"
        api.create_section.assert_awaited_once()


class TestSummarySelection:
    """Summary work follows summary state, independent of parsing."""

    @pytest.mark.asyncio
    async def test_selects_only_papers_without_an_abstract_summary(self):
        from preprint_bot.pipeline import _papers_needing_summary

        summaries = {
            1: [],  # parsed by an interrupted run, never summarized -> retried
            2: [{"mode": "abstract"}],  # already summarized -> not redone
            3: [{"mode": "full"}],  # only a different mode -> still needed
        }
        api = AsyncMock()
        api.get_summaries_by_paper.side_effect = lambda pid: summaries[pid]
        assert await _papers_needing_summary(api, {1, 2, 3}) == {1, 3}
