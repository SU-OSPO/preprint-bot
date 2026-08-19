"""Tests for ArxivSource identity, URLs, and taxonomy (no network)."""
from preprint_sources import ArxivSource


def test_identity():
    src = ArxivSource()
    assert src.name == "arxiv"
    assert src.label == "arXiv"


def test_landing_url():
    assert ArxivSource().landing_url("2401.12345") == "https://arxiv.org/abs/2401.12345"


def test_category_tree_is_nested_and_nonempty():
    tree = ArxivSource().category_tree()
    assert isinstance(tree, list) and tree
    top = tree[0]
    assert {"label", "value"} <= set(top)
    assert "children" in top and top["children"]      # nested taxonomy


def test_leaf_codes_and_labels():
    src = ArxivSource()
    codes = src.leaf_codes()
    assert "cs.AI" in codes
    assert "cs.LG" in codes
    # a leaf resolves to a human label distinct from the bare code
    assert src.label_for("cs.AI") != "cs.AI"
    # unknown code falls back to itself
    assert src.label_for("not.a.code") == "not.a.code"


def test_optional_capabilities_off_by_default():
    src = ArxivSource()
    assert src.supports_search() is False
    assert src.supports_add_by_id() is False
