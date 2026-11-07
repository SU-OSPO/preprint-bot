"""Tests for arXiv, bioRxiv and medRxiv taxonomy data (well-formedness, not exact contents)."""

from preprint_sources.taxonomies.arxiv import (
    ARXIV_CATEGORY_TREE,
    ARXIV_CODE_TO_LABEL,
    ARXIV_LEAF_CODES,
    label_for,
)
from preprint_sources.taxonomies.biorxiv import (
    BIORXIV_CATEGORY_TREE,
    BIORXIV_CODE_TO_LABEL,
    BIORXIV_LEAF_CODES,
)
from preprint_sources.taxonomies.biorxiv import label_for as biorxiv_label_for
from preprint_sources.taxonomies.medrxiv import (
    MEDRXIV_CATEGORY_TREE,
    MEDRXIV_CODE_TO_LABEL,
    MEDRXIV_LEAF_CODES,
)
from preprint_sources.taxonomies.medrxiv import label_for as medrxiv_label_for


def _iter_nodes(nodes):
    for n in nodes:
        yield n
        if n.get("children"):
            yield from _iter_nodes(n["children"])


def _leaf_values(nodes):
    for n in nodes:
        if n.get("children"):
            yield from _leaf_values(n["children"])
        else:
            yield n["value"]


def test_every_node_has_label_and_value():
    for node in _iter_nodes(ARXIV_CATEGORY_TREE):
        assert "label" in node and node["label"]
        assert "value" in node and node["value"]


def test_no_duplicate_leaf_values():
    leaves = list(_leaf_values(ARXIV_CATEGORY_TREE))
    assert len(leaves) == len(set(leaves))


def test_leaf_codes_nonempty_and_labeled():
    assert ARXIV_LEAF_CODES
    for code in ARXIV_LEAF_CODES:
        assert code in ARXIV_CODE_TO_LABEL
        assert label_for(code) == ARXIV_CODE_TO_LABEL[code]


def test_known_codes_present():
    assert {"cs.AI", "cs.LG"} <= ARXIV_LEAF_CODES


def test_label_for_unknown_returns_code():
    assert label_for("zzz.NOPE") == "zzz.NOPE"


def test_biorxiv_every_node_has_label_and_value():
    for node in _iter_nodes(BIORXIV_CATEGORY_TREE):
        assert "label" in node and node["label"]
        assert "value" in node and node["value"]


def test_biorxiv_no_duplicate_leaf_values():
    leaves = list(_leaf_values(BIORXIV_CATEGORY_TREE))
    assert len(leaves) == len(set(leaves))


def test_biorxiv_leaf_codes_nonempty_and_labeled():
    assert BIORXIV_LEAF_CODES
    for code in BIORXIV_LEAF_CODES:
        assert code in BIORXIV_CODE_TO_LABEL
        assert biorxiv_label_for(code) == BIORXIV_CODE_TO_LABEL[code]


def test_biorxiv_known_codes_present():
    # Multi-word values are spelled as the API returns them: lowercase, spaces.
    assert {"neuroscience", "cell biology"} <= BIORXIV_LEAF_CODES


def test_biorxiv_label_for_unknown_returns_code():
    assert biorxiv_label_for("zzz.nope") == "zzz.nope"


def test_medrxiv_every_node_has_label_and_value():
    for node in _iter_nodes(MEDRXIV_CATEGORY_TREE):
        assert "label" in node and node["label"]
        assert "value" in node and node["value"]


def test_medrxiv_no_duplicate_leaf_values():
    leaves = list(_leaf_values(MEDRXIV_CATEGORY_TREE))
    assert len(leaves) == len(set(leaves))


def test_medrxiv_leaf_codes_nonempty_and_labeled():
    assert MEDRXIV_LEAF_CODES
    for code in MEDRXIV_LEAF_CODES:
        assert code in MEDRXIV_CODE_TO_LABEL
        assert medrxiv_label_for(code) == MEDRXIV_CODE_TO_LABEL[code]


def test_medrxiv_known_codes_present():
    assert {
        "epidemiology",
        "endocrinology",
        "hiv aids",
        "infectious diseases",
    } <= MEDRXIV_LEAF_CODES


def test_medrxiv_label_for_unknown_returns_code():
    assert medrxiv_label_for("zzz.nope") == "zzz.nope"
