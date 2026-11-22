"""Tests for BiorxivSource identity, URLs, taxonomy, and id parsing (no network)."""

import pytest

from preprint_sources.biorxiv import BiorxivSource
from preprint_sources.taxonomies.biorxiv import (
    BIORXIV_CATEGORY_TREE,
    BIORXIV_LEAF_CODES,
)
from preprint_sources.taxonomies.biorxiv import label_for as biorxiv_label_for


def test_identity():
    src = BiorxivSource()
    assert src.name == "biorxiv"
    assert src.label == "bioRxiv"


def test_landing_url_is_versionless():
    assert (
        BiorxivSource().landing_url("10.64898/2026.10.25.761658")
        == "https://www.biorxiv.org/content/10.64898/2026.10.25.761658"
    )


def test_taxonomy_comes_from_the_biorxiv_module():
    src = BiorxivSource()
    assert src.category_tree() is BIORXIV_CATEGORY_TREE
    assert src.leaf_codes() is BIORXIV_LEAF_CODES
    for code in ("cell biology", "not a code"):
        assert src.label_for(code) == biorxiv_label_for(code)


def test_declared_capabilities():
    src = BiorxivSource()
    # No search API.
    assert src.supports_search() is False
    assert src.supports_add_by_id() is True
    assert "https://www.biorxiv.org/content/" in src.id_hint
    assert src.request_delay_seconds == 3.0


@pytest.mark.parametrize(
    "raw",
    [
        "10.64898/2026.10.25.761658",
        "10.64898/2026.10.25.761658v2",
        "  doi:10.64898/2026.10.25.761658 ",
        "DOI:10.64898/2026.10.25.761658",
        "https://doi.org/10.64898/2026.10.25.761658",
        "https://dx.doi.org/10.64898/2026.10.25.761658",
        "https://www.biorxiv.org/content/10.64898/2026.10.25.761658",
        "https://www.biorxiv.org/content/10.64898/2026.10.25.761658v1",
        "https://www.biorxiv.org/content/10.64898/2026.10.25.761658v1.full",
        "https://www.biorxiv.org/content/10.64898/2026.10.25.761658v1.full.pdf",
        "https://biorxiv.org/content/10.64898/2026.10.25.761658v3.abstract?versioned=true",
        "https://www.biorxiv.org/content/10.64898/2026.10.25.761658v1.full-text#sec-1",
    ],
)
def test_normalize_id_accepts_dois_and_biorxiv_urls(raw):
    assert BiorxivSource().normalize_id(raw) == "10.64898/2026.10.25.761658"


def test_normalize_id_accepts_the_old_prefix_and_numeric_ids():
    src = BiorxivSource()
    assert src.normalize_id("10.1101/2024.01.01.578123") == "10.1101/2024.01.01.578123"
    assert src.normalize_id("10.1101/339747v4") == "10.1101/339747"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "2301.12345",  # an arXiv id
        "10.1038/s41467-024-52215-7",  # a journal DOI
        "10.64898/not-a-doi",
        "https://www.medrxiv.org/content/10.64898/2026.10.25.26312345v1",  # the other server
        "https://example.com/content/10.64898/2026.10.25.761658",
    ],
)
def test_normalize_id_rejects_everything_else(raw):
    assert BiorxivSource().normalize_id(raw) is None
