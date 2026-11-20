"""Tests for the source registry."""

import importlib
import sys

import pytest

from preprint_sources import (
    ArxivSearchProvider,
    ArxivSource,
    BiorxivSource,
    MedrxivSource,
    PreprintSource,
    SearchProvider,
    all_search_provider_names,
    all_source_names,
    enabled_names,
    enabled_search_providers,
    enabled_sources,
    get_search_provider,
    get_source,
)


def test_arxiv_is_registered():
    assert "arxiv" in all_source_names()


def test_get_source_returns_instance():
    src = get_source("arxiv")
    assert isinstance(src, ArxivSource)
    assert isinstance(src, PreprintSource)


def test_biorxiv_is_registered():
    assert "biorxiv" in all_source_names()


def test_get_biorxiv_returns_instance():
    assert isinstance(get_source("biorxiv"), BiorxivSource)


def test_medrxiv_is_registered():
    assert "medrxiv" in all_source_names()


def test_get_medrxiv_returns_instance():
    assert isinstance(get_source("medrxiv"), MedrxivSource)


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


def test_enabled_dedupes_preserving_order(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv, arxiv")
    assert enabled_names() == ["arxiv"]
    assert [s.name for s in enabled_sources()] == ["arxiv"]


# ── Search providers ───────────────────────────────────────────────


def test_get_search_provider_returns_instance():
    provider = get_search_provider("arxiv")
    assert isinstance(provider, ArxivSearchProvider)
    assert isinstance(provider, SearchProvider)


def test_get_unknown_search_provider_raises():
    with pytest.raises(KeyError):
        get_search_provider("nope")


def test_search_providers_only_cover_registered_sources():
    for name in all_search_provider_names():
        assert set(get_search_provider(name).sources) <= set(all_source_names())


def test_search_provider_enabled_by_its_sources(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv,biorxiv")
    assert [p.name for p in enabled_search_providers()] == ["arxiv", "europepmc"]


def test_one_covered_source_is_enough(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "medrxiv")
    assert [p.name for p in enabled_search_providers()] == ["europepmc"]


def test_search_provider_disabled_without_its_sources(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv")
    assert [p.name for p in enabled_search_providers()] == ["arxiv"]


# ── The development-only demo source ───────────────────────────────


def _package_modules():
    return [
        name
        for name in list(sys.modules)
        if name == "preprint_sources" or name.startswith("preprint_sources.")
    ]


def _import_fresh():
    """Import the package with module-level registration re-run."""
    for name in _package_modules():
        del sys.modules[name]
    return importlib.import_module("preprint_sources")


@pytest.fixture
def reimport_registry():
    """Re-import the package, then put the original modules back.

    Registration happens at import time, so these tests have to reload the
    package. Re-importing again on teardown is not enough: other modules hold
    references to the original module objects, and ``importlib.reload`` on a
    stale reference fails once ``sys.modules`` holds a different object under
    the same name. So snapshot the real entries and restore them verbatim.
    """
    saved = {name: sys.modules[name] for name in _package_modules()}
    yield _import_fresh
    for name in _package_modules():
        del sys.modules[name]
    sys.modules.update(saved)


def test_demo_source_is_absent_by_default(monkeypatch, reimport_registry):
    """It must not even be registered, so it stays out of SOURCE_CHOICES."""
    monkeypatch.delenv("PREPRINT_ENABLED_SOURCES", raising=False)
    ps = reimport_registry()
    assert "demo" not in ps.all_source_names()
    with pytest.raises(KeyError):
        ps.get_source("demo")


def test_demo_source_registers_when_requested(monkeypatch, reimport_registry):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv,demo")
    ps = reimport_registry()
    assert ps.all_source_names() == ["arxiv", "biorxiv", "medrxiv", "demo"]
    assert ps.enabled_names() == ["arxiv", "demo"]

    demo = ps.get_source("demo")
    assert demo.label == "Demo Server"
    # Unsupported on purpose: this is how the add-paper tabs get exercised
    # hiding a capability a source lacks.
    assert demo.supports_add_by_id() is False
    assert "demo" not in [s for p in ps.enabled_search_providers() for s in p.sources]


async def test_demo_source_never_invents_papers(monkeypatch, reimport_registry):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv,demo")
    ps = reimport_registry()
    assert await ps.get_source("demo").fetch_latest(["neuro"]) == []


def test_demo_codes_are_independent_of_arxiv(monkeypatch, reimport_registry):
    """``cs.AI`` exists on both, and each must validate only its own."""
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv,demo")
    ps = reimport_registry()
    arxiv_codes = ps.get_source("arxiv").leaf_codes()
    demo_codes = ps.get_source("demo").leaf_codes()
    assert "cs.AI" in arxiv_codes and "cs.AI" in demo_codes
    assert "neuro" in demo_codes and "neuro" not in arxiv_codes
    assert "hep-th" in arxiv_codes and "hep-th" not in demo_codes
