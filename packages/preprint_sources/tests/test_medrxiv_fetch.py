"""Tests for MedrxivSource.fetch_latest / fetch_by_date with the network mocked."""

from datetime import date, datetime
from unittest.mock import ANY, AsyncMock, Mock, patch

import httpx
import pytest

from preprint_sources.medrxiv import MedrxivSource, _fetch_page

DAY = "2026-10-26"


def _record(doi, version="1", category="epidemiology"):
    return {
        "doi": doi,
        "title": "T",
        "authors": "A, B.",
        "date": DAY,
        "version": version,
        "category": category,
        "abstract": "",
    }


def _client(payload):
    """A stand-in httpx client whose get() returns *payload* as the JSON body."""
    client = AsyncMock()
    client.get.return_value = Mock(json=Mock(return_value=payload), raise_for_status=Mock())
    return client


class TestFetchPage:
    async def test_ok_returns_items_and_integer_total(self):
        client = _client(
            {"messages": [{"status": "ok", "total": "115"}], "collection": [_record("x")]}
        )
        assert await _fetch_page(client, DAY, 30) == ([_record("x")], 115)
        client.get.assert_awaited_once_with(
            f"https://api.biorxiv.org/details/medrxiv/{DAY}/{DAY}/30"
        )

    async def test_no_posts_found_is_an_empty_page(self):
        client = _client({"messages": [{"status": "no posts found"}]})
        assert await _fetch_page(client, DAY, 0) == ([], 0)

    async def test_error_status_raises(self):
        client = _client({"messages": [{"status": "Both dates must be in yyyy-mm-dd format"}]})
        with pytest.raises(RuntimeError, match="yyyy-mm-dd"):
            await _fetch_page(client, DAY, 0)

    async def test_http_error_raises(self):
        client = _client({})
        client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=Mock(), response=Mock()
        )
        with pytest.raises(httpx.HTTPStatusError):
            await _fetch_page(client, DAY, 0)


A = _record("10.64898/a")
B_V2 = _record("10.64898/b", version="2")
C_ONCOLOGY = _record("10.64898/c", category="oncology")


class TestFetchByDate:
    @patch("preprint_sources.medrxiv.asyncio.sleep", new_callable=AsyncMock)
    @patch("preprint_sources.medrxiv._fetch_page", new_callable=AsyncMock)
    async def test_pages_filter_and_dedupe(self, mock_page, mock_sleep):
        mock_page.side_effect = [([A, B_V2, C_ONCOLOGY], 4), ([A], 4)]

        out = await MedrxivSource().fetch_by_date(date(2026, 10, 26), ["epidemiology"])

        assert [e.source_id for e in out] == ["10.64898/a"]
        assert [c.args for c in mock_page.call_args_list] == [(ANY, DAY, 0), (ANY, DAY, 3)]
        mock_sleep.assert_awaited_once_with(3.0)

    @patch("preprint_sources.medrxiv.asyncio.sleep", new_callable=AsyncMock)
    @patch("preprint_sources.medrxiv._fetch_page", new_callable=AsyncMock)
    async def test_empty_page_stops_even_if_total_says_more(self, mock_page, _mock_sleep):
        mock_page.side_effect = [([], 5)]
        assert await MedrxivSource().fetch_by_date(date(2026, 10, 26), ["epidemiology"]) == []
        assert mock_page.await_count == 1

    @patch("preprint_sources.medrxiv._fetch_page", new_callable=AsyncMock)
    async def test_datetime_input_gives_the_same_day(self, mock_page):
        mock_page.return_value = ([], 0)
        await MedrxivSource().fetch_by_date(datetime(2026, 10, 26), ["epidemiology"])
        assert mock_page.call_args.args == (ANY, DAY, 0)

    @patch("preprint_sources.medrxiv._fetch_page", new_callable=AsyncMock)
    async def test_page_error_propagates(self, mock_page):
        mock_page.side_effect = RuntimeError("medRxiv API error")
        with pytest.raises(RuntimeError):
            await MedrxivSource().fetch_by_date(date(2026, 10, 26), ["epidemiology"])


@patch("preprint_sources.medrxiv._yesterday_et", return_value=date(2026, 10, 26))
async def test_fetch_latest_fetches_yesterday(_mock_yesterday):
    with patch.object(MedrxivSource, "fetch_by_date", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []
        await MedrxivSource().fetch_latest(["epidemiology"])
    mock_fetch.assert_awaited_once_with(date(2026, 10, 26), ["epidemiology"])
