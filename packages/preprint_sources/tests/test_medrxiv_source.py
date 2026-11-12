"""Tests for MedrxivSource identity, URLs, and taxonomy (no network)."""

from preprint_sources.medrxiv import MedrxivSource
from preprint_sources.taxonomies.medrxiv import (
    MEDRXIV_CATEGORY_TREE,
    MEDRXIV_LEAF_CODES,
)
from preprint_sources.taxonomies.medrxiv import label_for as medrxiv_label_for


def test_identity():
    src = MedrxivSource()
    assert src.name == "medrxiv"
    assert src.label == "medRxiv"


def test_landing_url_is_versionless():
    assert (
        MedrxivSource().landing_url("10.64898/2026.10.25.26312345")
        == "https://www.medrxiv.org/content/10.64898/2026.10.25.26312345"
    )


def test_taxonomy_comes_from_the_medrxiv_module():
    src = MedrxivSource()
    assert src.category_tree() is MEDRXIV_CATEGORY_TREE
    assert src.leaf_codes() is MEDRXIV_LEAF_CODES
    for code in ("hiv aids", "not a code"):
        assert src.label_for(code) == medrxiv_label_for(code)


def test_declared_capabilities():
    src = MedrxivSource()
    assert src.supports_search() is False
    assert src.supports_add_by_id() is False
    assert src.request_delay_seconds == 3.0
