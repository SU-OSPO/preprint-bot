"""Tests for EuropePmcSearchProvider with the API mocked."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from preprint_sources import EuropePmcSearchProvider
from preprint_sources.europepmc import _entry_from_result, _fetch_page, _phrase_term


def _result(doi, publisher="bioRxiv", authors="Swarna NP, Pachter L.", id_="PPR1"):
    """A lite search result, shaped like the API's (values made up)."""
    return {
        "id": id_,
        "doi": doi,
        "title": " A Title ",
        "authorString": authors,
        "firstPublicationDate": "2026-11-18",
        "bookOrReportDetails": {"publisher": publisher},
    }


def _mock_client():
    """A stand-in httpx.AsyncClient usable as an async context manager."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def test_identity():
    provider = EuropePmcSearchProvider()
    assert provider.name == "europepmc"
    assert provider.label == "Europe PMC"
    assert provider.sources == ["biorxiv", "medrxiv"]
    assert provider.request_delay_seconds == 3.0


def test_phrase_term_drops_quotes_and_backslashes():
    assert _phrase_term("TITLE", '  sneaky" OR \\ all ') == 'TITLE:"sneaky OR all"'


class TestEntryFromResult:
    def test_converts_a_covered_preprint(self):
        entry = _entry_from_result(_result("10.64898/2026.11.16.767160", publisher="medRxiv"))
        assert entry.source == "medrxiv"
        assert entry.source_id == "10.64898/2026.11.16.767160"
        assert entry.title == "A Title"
        assert entry.authors == ["Swarna NP", "Pachter L"]  # trailing period dropped
        assert entry.published == "2026-11-18"
        assert entry.url == "https://doi.org/10.64898/2026.11.16.767160"
        assert entry.pdf_url == ""
        assert entry.metadata == {"europepmc_id": "PPR1"}

    def test_title_markup_is_removed(self):
        item = {**_result("10.1/a"), "title": "The 3 <sup>rd</sup> wave of COVID &amp; flu "}
        assert _entry_from_result(item).title == "The 3 rd wave of COVID & flu"

    def test_other_servers_and_missing_dois_are_skipped(self):
        assert _entry_from_result(_result("10.21203/rs.3", publisher="Research Square")) is None
        assert _entry_from_result({**_result("x"), "doi": None}) is None
        assert _entry_from_result({"doi": "10.1101/1"}) is None


class TestSearch:
    @patch("preprint_sources.europepmc._fetch_page", new_callable=AsyncMock)
    @patch("preprint_sources.europepmc.httpx.AsyncClient")
    async def test_builds_query_for_both_fields(self, mock_client, mock_page):
        mock_client.return_value = _mock_client()
        mock_page.return_value = ([], None)
        await EuropePmcSearchProvider().search(title="single-cell", author="Regev, A.")

        query = mock_page.call_args.args[1]
        assert query == (
            'SRC:PPR AND (PUBLISHER:"bioRxiv" OR PUBLISHER:"medRxiv")'
            ' AND TITLE:"single-cell" AND AUTH:"Regev A"'
        )

    @patch("preprint_sources.europepmc._fetch_page", new_callable=AsyncMock)
    @patch("preprint_sources.europepmc.httpx.AsyncClient")
    async def test_sources_narrow_the_servers(self, mock_client, mock_page):
        mock_client.return_value = _mock_client()
        mock_page.return_value = ([], None)
        await EuropePmcSearchProvider().search(title="x", sources=["medrxiv", "arxiv"])
        assert '(PUBLISHER:"medRxiv")' in mock_page.call_args.args[1]

    @patch("preprint_sources.europepmc._fetch_page", new_callable=AsyncMock)
    async def test_no_covered_sources_makes_no_request(self, mock_page):
        assert await EuropePmcSearchProvider().search(title="x", sources=["arxiv"]) == []
        mock_page.assert_not_called()

    async def test_requires_a_term(self):
        with pytest.raises(ValueError):
            await EuropePmcSearchProvider().search(author="  ")

    @patch("preprint_sources.europepmc.asyncio.sleep", new_callable=AsyncMock)
    @patch("preprint_sources.europepmc._fetch_page", new_callable=AsyncMock)
    @patch("preprint_sources.europepmc.httpx.AsyncClient")
    async def test_pages_until_the_cursor_repeats(self, mock_client, mock_page, mock_sleep):
        mock_client.return_value = _mock_client()
        mock_page.side_effect = [
            ([_result("10.1/a"), _result("10.1/b", publisher="Research Square")], "c1"),
            ([_result("10.1/a"), _result("10.1/c")], "c2"),  # 10.1/a again: deduped
            ([_result("10.1/d")], "c2"),  # last page repeats its own cursor
        ]
        results = await EuropePmcSearchProvider().search(title="x")
        assert [r.source_id for r in results] == ["10.1/a", "10.1/c", "10.1/d"]
        assert [c.args[2] for c in mock_page.call_args_list] == ["*", "c1", "c2"]
        assert mock_sleep.await_count == 2  # before each page after the first

    @patch("preprint_sources.europepmc._fetch_page", new_callable=AsyncMock)
    @patch("preprint_sources.europepmc.httpx.AsyncClient")
    async def test_stops_at_max_results(self, mock_client, mock_page):
        mock_client.return_value = _mock_client()
        mock_page.return_value = ([_result(f"10.1/{i}") for i in range(5)], "next")
        results = await EuropePmcSearchProvider().search(title="x", max_results=3)
        assert len(results) == 3
        assert mock_page.await_count == 1
        assert mock_page.call_args.args[3] == 3  # page size capped at max_results


class TestFetchPage:
    def _client(self, payload):
        client = AsyncMock()
        client.get.return_value = Mock(json=Mock(return_value=payload), raise_for_status=Mock())
        return client

    async def test_returns_results_and_next_cursor(self):
        client = self._client(
            {"resultList": {"result": [_result("10.1/a")]}, "nextCursorMark": "c1"}
        )
        assert await _fetch_page(client, "q", "*", 1000) == ([_result("10.1/a")], "c1")
        params = client.get.call_args.kwargs["params"]
        assert params["cursorMark"] == "*"
        assert params["pageSize"] == 1000
        assert params["sort"] == "P_PDATE_D desc"

    async def test_err_msg_raises(self):
        client = self._client({"errMsg": "Invalid page size provided."})
        with pytest.raises(RuntimeError, match="Invalid page size"):
            await _fetch_page(client, "q", "*", 1001)

    async def test_http_error_raises(self):
        client = self._client({})
        client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=Mock(), response=Mock()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_page(client, "q", "*", 10)
