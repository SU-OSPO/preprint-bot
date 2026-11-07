"""Tests for BiorxivSource identity, URLs, and taxonomy (no network)."""

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
    # No search API, and add-by-id is left for a later PR.
    assert src.supports_search() is False
    assert src.supports_add_by_id() is False
    assert src.request_delay_seconds == 3.0
