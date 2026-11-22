"""Tests for the SearchProvider ABC contract."""

import pytest

from preprint_sources import ArxivSearchProvider, SearchProvider


def test_cannot_instantiate_bare_abstract_base():
    with pytest.raises(TypeError):
        SearchProvider()


class _Minimal(SearchProvider):
    @property
    def name(self):
        return "min"

    @property
    def label(self):
        return "Min"

    @property
    def sources(self):
        return ["min"]

    async def search(self, *, title="", author="", max_results=100):
        return []


def test_request_delay_defaults_to_zero():
    assert _Minimal().request_delay_seconds == 0.0


def test_arxiv_provider_identity():
    provider = ArxivSearchProvider()
    assert provider.name == "arxiv"
    assert provider.label == "arXiv"
    assert provider.sources == ["arxiv"]
    assert provider.request_delay_seconds == 3.0  # arXiv asks for 1 req / 3s
