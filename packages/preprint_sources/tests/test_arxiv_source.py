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


def test_declared_capabilities():
    src = ArxivSource()
    assert src.supports_search() is True
    assert src.supports_add_by_id() is True
    assert src.id_hint                      # placeholder examples for the UI
    assert src.request_delay_seconds == 3.0  # arXiv asks for 1 req / 3s


def test_normalize_id_accepts_bare_ids():
    src = ArxivSource()
    assert src.normalize_id("2301.12345") == "2301.12345"
    assert src.normalize_id("2301.1234") == "2301.1234"
    assert src.normalize_id("hep-th/9901001") == "hep-th/9901001"
    assert src.normalize_id("math.GT/0309136") == "math.GT/0309136"


def test_normalize_id_strips_prefixes_and_suffixes():
    src = ArxivSource()
    assert src.normalize_id("https://arxiv.org/abs/2601.19018") == "2601.19018"
    assert src.normalize_id("https://arxiv.org/pdf/2601.19018v2.pdf") == "2601.19018"
    assert src.normalize_id("arXiv:2601.19018") == "2601.19018"
    assert src.normalize_id("ARXIV:2301.12345") == "2301.12345"
    assert src.normalize_id("2601.19018v12") == "2601.19018"
    assert src.normalize_id("https://arxiv.org/abs/2601.19018#section1") == "2601.19018"
    assert src.normalize_id("https://arxiv.org/pdf/hep-th/9901001v2.pdf?download") == "hep-th/9901001"


def test_normalize_id_rejects_non_ids():
    src = ArxivSource()
    for raw in ("", "   ", "not-an-id", "hello world", "12345", "2301.1", "2301.123456"):
        assert src.normalize_id(raw) is None
