"""Tests for ArxivSource.search / fetch_one / fetch_many with the API mocked."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from preprint_sources import ArxivSource


def _mock_async_client():
    """A stand-in for httpx.AsyncClient usable as an async context manager."""
    client = AsyncMock()
    client.get.return_value = Mock(
        text="<feed/>", status_code=200, headers={}, raise_for_status=Mock()
    )
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _api_item(
    entry_id, title="A Title", summary="An abstract.", authors=("Ada Lovelace",), tags=("cs.AI",)
):
    """An arXiv API result as feedparser hands it back."""
    return SimpleNamespace(
        id=entry_id,
        title=title,
        summary=summary,
        authors=[SimpleNamespace(name=n) for n in authors],
        tags=[SimpleNamespace(term=t) for t in tags],
        published="2024-01-02T00:00:00Z",
    )


class TestSearch:
    @patch("preprint_sources.arxiv._api_fetch_all", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_builds_phrase_query_for_both_fields(self, mock_client, mock_fetch):
        mock_client.return_value = _mock_async_client()
        mock_fetch.return_value = []
        await ArxivSource().search(title="deep learning", author="LeCun", max_results=25)

        query = mock_fetch.call_args.args[1]
        assert "ti:%22deep%20learning%22" in query
        assert "au:%22LeCun%22" in query
        assert "+AND+" in query
        assert mock_fetch.call_args.kwargs["limit"] == 25

    @patch("preprint_sources.arxiv._api_fetch_all", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_quotes_in_user_input_cannot_break_the_phrase(self, mock_client, mock_fetch):
        mock_client.return_value = _mock_async_client()
        mock_fetch.return_value = []
        await ArxivSource().search(title='sneaky" OR all:')

        query = mock_fetch.call_args.args[1]
        assert query.count("%22") == 2  # exactly the phrase's own quotes

    @patch("preprint_sources.arxiv._api_fetch_all", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_converts_results_and_drops_duplicates(self, mock_client, mock_fetch):
        mock_client.return_value = _mock_async_client()
        mock_fetch.return_value = [
            _api_item("http://arxiv.org/abs/2401.00001v2", title="First"),
            _api_item("http://arxiv.org/abs/2401.00001v1", title="First again"),
            _api_item("http://arxiv.org/api/errors#bad", title="Error"),
        ]
        results = await ArxivSource().search(title="x")

        assert [r.source_id for r in results] == ["2401.00001"]  # deduped, error dropped
        assert results[0].title == "First"
        assert results[0].pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"
        assert results[0].source == "arxiv"

    async def test_requires_a_term(self):
        with pytest.raises(ValueError):
            await ArxivSource().search()


class TestFetchByIds:
    @patch("preprint_sources.arxiv._api_fetch_by_ids", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_fetch_many_keys_by_canonical_id(self, mock_client, mock_fetch):
        mock_client.return_value = _mock_async_client()
        mock_fetch.return_value = [
            _api_item("http://arxiv.org/abs/2401.00001v3", title="One"),
            _api_item("http://arxiv.org/abs/2401.00002", title="Two"),
        ]
        entries = await ArxivSource().fetch_many(["2401.00001", "2401.00002"])

        assert set(entries) == {"2401.00001", "2401.00002"}
        assert entries["2401.00001"].title == "One"

    @patch("preprint_sources.arxiv._api_fetch_by_ids", new_callable=AsyncMock)
    @patch("preprint_sources.arxiv.httpx.AsyncClient")
    async def test_fetch_one_returns_none_for_unknown_id(self, mock_client, mock_fetch):
        mock_client.return_value = _mock_async_client()
        mock_fetch.return_value = [_api_item("http://arxiv.org/api/errors#bad", title="Error")]
        assert await ArxivSource().fetch_one("2401.99999") is None

    async def test_fetch_many_short_circuits_on_empty_input(self):
        assert await ArxivSource().fetch_many([]) == {}
