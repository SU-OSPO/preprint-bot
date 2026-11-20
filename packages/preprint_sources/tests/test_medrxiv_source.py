"""Tests for MedrxivSource identity, URLs, taxonomy, and id parsing (no network)."""

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
    assert src.supports_add_by_id() is True
    assert "https://www.medrxiv.org/content/" in src.id_hint
    assert src.request_delay_seconds == 3.0


def test_normalize_id_accepts_medrxiv_urls_and_dois():
    src = MedrxivSource()
    doi = "10.64898/2026.10.25.26312345"
    assert src.normalize_id(f"https://www.medrxiv.org/content/{doi}v2.full.pdf") == doi
    assert src.normalize_id(f"doi:{doi}") == doi
    assert src.normalize_id("10.1101/2020.03.19.20039123") == "10.1101/2020.03.19.20039123"


def test_normalize_id_rejects_biorxiv_urls():
    url = "https://www.biorxiv.org/content/10.64898/2026.10.25.761658v1"
    assert MedrxivSource().normalize_id(url) is None
