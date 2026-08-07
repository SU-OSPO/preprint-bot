"""Tests for the source registry."""
import pytest

from preprint_sources import (
    ArxivSource,
    PreprintSource,
    all_source_names,
    enabled_names,
    enabled_sources,
    get_source,
)


def test_arxiv_is_registered():
    assert "arxiv" in all_source_names()


def test_get_source_returns_instance():
    src = get_source("arxiv")
    assert isinstance(src, ArxivSource)
    assert isinstance(src, PreprintSource)


def test_get_unknown_source_raises():
    with pytest.raises(KeyError):
        get_source("nope")


def test_enabled_defaults_to_arxiv(monkeypatch):
    monkeypatch.delenv("PREPRINT_ENABLED_SOURCES", raising=False)
    assert enabled_names() == ["arxiv"]
    assert [s.name for s in enabled_sources()] == ["arxiv"]


def test_enabled_reads_env_and_drops_unknown(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv, bogus")
    assert enabled_names() == ["arxiv"]
