"""Tests for the arXiv taxonomy data (well-formedness, not exact contents)."""
from preprint_sources.taxonomies.arxiv import (
    ARXIV_CATEGORY_TREE,
    ARXIV_CODE_TO_LABEL,
    ARXIV_LEAF_CODES,
    label_for,
)


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
