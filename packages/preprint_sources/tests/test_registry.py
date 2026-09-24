"""Tests for the source registry."""

import importlib
import sys

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


def test_enabled_dedupes_preserving_order(monkeypatch):
    monkeypatch.setenv("PREPRINT_ENABLED_SOURCES", "arxiv, arxiv")
    assert enabled_names() == ["arxiv"]
    assert [s.name for s in enabled_sources()] == ["arxiv"]


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
    assert ps.all_source_names() == ["arxiv", "demo"]
    assert ps.enabled_names() == ["arxiv", "demo"]

    demo = ps.get_source("demo")
    assert demo.label == "Demo Server"
    # Unsupported on purpose: this is how the add-paper tabs get exercised
    # hiding a capability a source lacks.
    assert demo.supports_search() is False
    assert demo.supports_add_by_id() is False


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
