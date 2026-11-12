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
    client.get.return_value = Mock(
        text="<rss/>", status_code=200, headers={}, raise_for_status=Mock()
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _rss_item(
    link,
    announce="new",
    title="arXiv:x A Title",
    description="<p>Body.</p>",
    author="Ada Lovelace",
    tags=("cs.AI",),
):
    return SimpleNamespace(
        link=link,
        title=title,
        description=description,
        arxiv_announce_type=announce,
        author=author,
        tags=[SimpleNamespace(term=t) for t in tags],
        published="2024-01-02T00:00:00Z",
    )


class TestFetchLatest:
    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_parses_new_item_into_paper_entry(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed(
            [
                _rss_item(
                    "https://arxiv.org/abs/2401.00001v2",
                    title="arXiv:2401.00001 A New Result",
                    description="<p>We show something.</p>",
                    author="Ada Lovelace, Alan Turing",
                ),
            ]
        )
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert len(papers) == 1
        p = papers[0]
        assert p.source_id == "2401.00001"  # version stripped
        assert p.title == "A New Result"  # arXiv: prefix stripped
        assert p.abstract == "We show something."  # HTML stripped
        assert p.pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"
        assert p.authors == ["Ada Lovelace", "Alan Turing"]
        assert p.categories == ["cs.AI"]
        assert p.source == "arxiv"

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_skips_non_new_announce_types(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed(
            [
                _rss_item("https://arxiv.org/abs/2401.00001", announce="new"),
                _rss_item("https://arxiv.org/abs/2401.00002", announce="replace"),
                _rss_item("https://arxiv.org/abs/2401.00003", announce="cross"),
            ]
        )
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert [p.source_id for p in papers] == ["2401.00001"]

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_dedupes_by_arxiv_id(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed(
            [
                _rss_item("https://arxiv.org/abs/2401.00001v1"),
                _rss_item("https://arxiv.org/abs/2401.00001v2"),  # same id, other version
            ]
        )
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert len(papers) == 1

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_skips_items_without_arxiv_id(self, mock_client, mock_parse):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _feed([_rss_item("https://example.com/no-abs")])
        assert await ArxivSource().fetch_latest(["cs.AI"]) == []

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_request_bypasses_cdn_cache(self, mock_client, mock_parse):
        cm = _mock_async_client()
        mock_client.return_value = cm
        mock_parse.return_value = _feed([])
        await ArxivSource().fetch_latest(["cs.AI"])
        call = cm.__aenter__.return_value.get.call_args
        assert call.args[0] == "https://rss.arxiv.org/rss/cs.AI"
        assert call.kwargs["params"]["t"]


def _capped_feed(n_new=10):
    """A feed at the entry cap: *n_new* new items, the rest replacements."""
    from preprint_sources.arxiv import _RSS_MAX_ENTRIES

    items = [_rss_item(f"https://arxiv.org/abs/2401.{i:05d}") for i in range(n_new)]
    items += [
        _rss_item(f"https://arxiv.org/abs/2312.{i:05d}", announce="replace")
        for i in range(_RSS_MAX_ENTRIES - n_new)
    ]
    return _feed(items)


class TestFetchLatestEntryCap:
    @patch("preprint_sources.arxiv.asyncio.sleep", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_capped_feed_is_split_and_merged(self, mock_client, mock_parse, mock_sleep):
        cm = _mock_async_client()
        mock_client.return_value = cm
        mock_parse.side_effect = [
            _capped_feed(),
            _feed([_rss_item("https://arxiv.org/abs/2401.10001")]),
            _feed(
                [
                    _rss_item("https://arxiv.org/abs/2401.10002"),
                    # cross-listed into the first half's category; not new here
                    _rss_item("https://arxiv.org/abs/2401.10001", announce="cross"),
                ]
            ),
        ]
        papers = await ArxivSource().fetch_latest(["cs.AI", "cs.LG", "cs.CV"])

        urls = [c.args[0] for c in cm.__aenter__.return_value.get.call_args_list]
        assert urls == [
            "https://rss.arxiv.org/rss/cs.AI+cs.LG+cs.CV",
            "https://rss.arxiv.org/rss/cs.AI",
            "https://rss.arxiv.org/rss/cs.LG+cs.CV",
        ]
        # The truncated feed's entries are discarded in favour of the halves'.
        assert [p.source_id for p in papers] == ["2401.10001", "2401.10002"]
        assert mock_sleep.await_count == 2  # rate limit between the refetches

    @patch("preprint_sources.arxiv.feedparser.parse")
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_capped_single_category_warns_and_keeps_entries(
        self, mock_client, mock_parse, caplog
    ):
        mock_client.return_value = _mock_async_client()
        mock_parse.return_value = _capped_feed(n_new=3)
        papers = await ArxivSource().fetch_latest(["cs.AI"])
        assert len(papers) == 3
        assert "cs.AI hit the 2000-entry cap" in caplog.text


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
        mock_fetch_all.return_value = [
            SimpleNamespace(
                id="http://arxiv.org/abs/2401.09999v1",
                title="  API Paper  ",
                summary="  An abstract.  ",
                authors=[SimpleNamespace(name="Grace Hopper")],
                tags=[SimpleNamespace(term="cs.SE")],
                published="2024-01-01T00:00:00Z",
            )
        ]
        papers = await ArxivSource().fetch_by_date(date(2024, 1, 2), ["cs.SE"])
        assert len(papers) == 1
        p = papers[0]
        # Version stripped, consistent with the RSS path (fetch_latest).
        assert p.source_id == "2401.09999"
        assert p.title == "API Paper"
        assert p.abstract == "An abstract."
        assert p.authors == ["Grace Hopper"]
        assert p.categories == ["cs.SE"]
        assert p.pdf_url == "https://arxiv.org/pdf/2401.09999.pdf"
