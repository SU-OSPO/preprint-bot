"""Tests for ArxivSource.fetch_latest / fetch_by_date with the network mocked."""
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from preprint_sources import ArxivSource


def _feed(entries):
    return SimpleNamespace(entries=entries, feed={})


def _mock_async_client():
    """A stand-in for httpx.AsyncClient usable as an async context manager."""
    client = AsyncMock()
    client.get.return_value = Mock(text="<rss/>", status_code=200,
                                   headers={}, raise_for_status=Mock())
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _rss_item(link, announce="new", title="arXiv:x A Title",
              description="<p>Body.</p>", author="Ada Lovelace", tags=("cs.AI",)):
    return SimpleNamespace(
        link=link, title=title, description=description,
        arxiv_announce_type=announce, author=author,
        tags=[SimpleNamespace(term=t) for t in tags], published="2024-01-02T00:00:00Z",
    )


class TestFetchLatest:
    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_parses_new_item_into_paper_entry(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed([
            _rss_item("https://arxiv.org/abs/2401.00001v2",
                      title="arXiv:2401.00001 A New Result",
                      description="<p>We show something.</p>",
                      author="Ada Lovelace, Alan Turing"),
        ])
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert len(papers) == 1
        p = papers[0]
        assert p.source_id == "2401.00001"                       # version stripped
        assert p.title == "A New Result"                         # arXiv: prefix stripped
        assert p.abstract == "We show something."                # HTML stripped
        assert p.pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"
        assert p.authors == ["Ada Lovelace", "Alan Turing"]
        assert p.categories == ["cs.AI"]
        assert p.source == "arxiv"

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_skips_non_new_announce_types(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed([
            _rss_item("https://arxiv.org/abs/2401.00001", announce="new"),
            _rss_item("https://arxiv.org/abs/2401.00002", announce="replace"),
            _rss_item("https://arxiv.org/abs/2401.00003", announce="cross"),
        ])
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert [p.source_id for p in papers] == ["2401.00001"]

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_dedupes_by_arxiv_id(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed([
            _rss_item("https://arxiv.org/abs/2401.00001v1"),
            _rss_item("https://arxiv.org/abs/2401.00001v2"),   # same id, other version
        ])
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert len(papers) == 1

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_skips_items_without_arxiv_id(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed([_rss_item("https://example.com/no-abs")])
        assert await ArxivSource().fetch_latest(["cs.AI"]) == []


class TestFetchByDate:
    @patch("preprint_sources.arxiv._get_announcement_window", return_value=None)
    async def test_no_announcement_returns_empty(self, _mock_window):
        # Friday has no announcement window -> returns before any network call.
        assert await ArxivSource().fetch_by_date(date(2024, 1, 5), ["cs.AI"]) == []

    @patch("preprint_sources.arxiv._api_fetch_all")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    @patch("preprint_sources.arxiv._get_announcement_window")
    async def test_builds_entries_from_api(self, mock_window, mock_client, mock_fetch_all):
        mock_window.return_value = (
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        mock_client.return_value = _mock_async_client()
        mock_fetch_all.return_value = [SimpleNamespace(
            id="http://arxiv.org/abs/2401.09999v1",
            title="  API Paper  ",
            summary="  An abstract.  ",
            authors=[SimpleNamespace(name="Grace Hopper")],
            tags=[SimpleNamespace(term="cs.SE")],
            published="2024-01-01T00:00:00Z",
        )]
        papers = await ArxivSource().fetch_by_date(date(2024, 1, 2), ["cs.SE"])
        assert len(papers) == 1
        p = papers[0]
        # API path keeps the version suffix (unlike the RSS path).
        assert p.source_id == "2401.09999v1"
        assert p.title == "API Paper"
        assert p.abstract == "An abstract."
        assert p.authors == ["Grace Hopper"]
        assert p.categories == ["cs.SE"]
        assert p.pdf_url == "https://arxiv.org/pdf/2401.09999v1.pdf"
