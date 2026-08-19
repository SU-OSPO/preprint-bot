"""Tests for the PreprintSource ABC contract and PaperEntry."""
import pytest

from preprint_sources import PaperEntry, PreprintSource


def test_paper_entry_defaults_metadata():
    e = PaperEntry(
        source_id="1", title="t", abstract="a", url="u", pdf_url="p",
        authors=["x"], categories=["c"], published="d", source="arxiv",
    )
    assert e.metadata == {}          # default_factory=dict


def test_cannot_instantiate_bare_abstract_base():
    with pytest.raises(TypeError):
        PreprintSource()


def test_incomplete_subclass_cannot_instantiate():
    class Partial(PreprintSource):
        @property
        def name(self):
            return "partial"
        # missing label/fetch_latest/landing_url/category_tree/leaf_codes

    with pytest.raises(TypeError):
        Partial()


class _Minimal(PreprintSource):
    """A complete-but-minimal source for exercising the optional defaults."""

    @property
    def name(self):
        return "min"

    @property
    def label(self):
        return "Min"

    async def fetch_latest(self, categories):
        return []

    def landing_url(self, source_id):
        return source_id

    def category_tree(self):
        return []

    def leaf_codes(self):
        return set()


def test_optional_capabilities_default_off():
    src = _Minimal()
    assert src.supports_search() is False
    assert src.supports_add_by_id() is False
    assert src.label_for("code") == "code"


async def test_optional_methods_raise_not_implemented():
    src = _Minimal()
    with pytest.raises(NotImplementedError):
        await src.fetch_by_date(None, [])
    with pytest.raises(NotImplementedError):
        await src.search(title="x")
    with pytest.raises(NotImplementedError):
        src.normalize_id("x")
    with pytest.raises(NotImplementedError):
        await src.fetch_one("x")
