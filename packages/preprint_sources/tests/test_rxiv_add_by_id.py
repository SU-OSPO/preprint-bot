"""Tests for bioRxiv/medRxiv add-by-id: DOI lookups with the API mocked."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from preprint_sources.biorxiv import BiorxivSource
from preprint_sources.medrxiv import MedrxivSource
from preprint_sources.rxiv import _entry_from_versions

DOI = "10.1101/339747"
SITE = "https://www.biorxiv.org"


def _version(version, date, title="T", category="microbiology"):
    """One version record, shaped like the API's (values made up)."""
    return {
        "doi": DOI,
        "title": f" {title} ",
        "authors": "Kvich, L. A.; Fritz, B. G.",
        "date": date,
        "version": version,
        "category": category,
        "abstract": " Body. ",
    }


def _mock_client(payload):
    """A stand-in httpx.AsyncClient context manager whose get() returns *payload*."""
    client = AsyncMock()
    client.get.return_value = Mock(json=Mock(return_value=payload), raise_for_status=Mock())
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


class TestEntryFromVersions:
    def test_latest_version_with_first_posting_date(self):
        records = [_version("2", "2019-02-07", title="Second"), _version("1", "2018-06-05")]
        entry = _entry_from_versions(records, SITE, "biorxiv")
        assert entry.source_id == DOI
        assert entry.title == "Second"
        assert entry.abstract == "Body."
        assert entry.url == f"{SITE}/content/{DOI}"
        assert entry.pdf_url == f"{SITE}/content/{DOI}v2.full.pdf"
        assert entry.authors == ["Kvich, L. A.", "Fritz, B. G."]
        assert entry.categories == ["microbiology"]
        assert entry.published == "2018-06-05T00:00:00-04:00"
        assert entry.source == "biorxiv"
        assert entry.metadata == {"posted": "2018-06-05"}

    def test_versions_compare_as_numbers(self):
        # "10" sorts before "9" as a string.
        records = [_version("9", "2020-01-01"), _version(10, "2020-02-01")]
        assert _entry_from_versions(records, SITE, "biorxiv").pdf_url.endswith("v10.full.pdf")

    def test_no_records_is_none(self):
        assert _entry_from_versions([], SITE, "biorxiv") is None


class TestFetchOne:
    async def test_looks_up_the_doi_on_its_server(self):
        cm, client = _mock_client(
            {"messages": [{"status": "ok"}], "collection": [_version("1", "2018-06-05")]}
        )
        with patch("preprint_sources.rxiv.httpx.AsyncClient", return_value=cm):
            entry = await MedrxivSource().fetch_one(DOI)
        client.get.assert_awaited_once_with(f"https://api.biorxiv.org/details/medrxiv/{DOI}")
        assert entry.source == "medrxiv"
        assert entry.pdf_url == f"https://www.medrxiv.org/content/{DOI}v1.full.pdf"

    async def test_unknown_doi_is_none(self):
        # Also what the API answers for a DOI that belongs to the other server.
        cm, _ = _mock_client({"messages": [{"status": "no posts found"}]})
        with patch("preprint_sources.rxiv.httpx.AsyncClient", return_value=cm):
            assert await BiorxivSource().fetch_one(DOI) is None

    async def test_error_status_raises(self):
        cm, _ = _mock_client({"messages": [{"status": "DOI not valid"}]})
        with patch("preprint_sources.rxiv.httpx.AsyncClient", return_value=cm):
            with pytest.raises(RuntimeError, match="DOI not valid"):
                await BiorxivSource().fetch_one(DOI)

    async def test_http_error_raises(self):
        cm, client = _mock_client({})
        client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=Mock(), response=Mock()
        )
        with patch("preprint_sources.rxiv.httpx.AsyncClient", return_value=cm):
            with pytest.raises(httpx.HTTPStatusError):
                await BiorxivSource().fetch_one(DOI)


@patch("preprint_sources.base.asyncio.sleep", new_callable=AsyncMock)
async def test_fetch_many_keys_by_doi_drops_unknown_and_paces(mock_sleep):
    known = _entry_from_versions([_version("1", "2018-06-05")], SITE, "biorxiv")
    with patch.object(
        BiorxivSource, "fetch_one", new_callable=AsyncMock, side_effect=[known, None]
    ):
        entries = await BiorxivSource().fetch_many([DOI, "10.1101/999999"])
    assert entries == {DOI: known}
    mock_sleep.assert_awaited_once_with(3.0)  # between the two lookups only
