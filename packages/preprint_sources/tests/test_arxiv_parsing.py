"""Unit tests for the pure arXiv parsing + date-window helpers."""
from datetime import date, timedelta
from types import SimpleNamespace

from preprint_sources.arxiv import (
    _clean_html,
    _clean_rss_title,
    _extract_arxiv_id,
    _get_announcement_window,
    _latex_to_unicode,
    _parse_rss_authors,
    _parse_rss_categories,
)


class TestExtractArxivId:
    def test_basic(self):
        assert _extract_arxiv_id("https://arxiv.org/abs/2401.12345") == "2401.12345"

    def test_strips_version(self):
        assert _extract_arxiv_id("https://arxiv.org/abs/2401.12345v3") == "2401.12345"

    def test_no_abs_returns_none(self):
        assert _extract_arxiv_id("https://example.com/nope") is None

    def test_none_input(self):
        assert _extract_arxiv_id(None) is None


class TestCleanRssTitle:
    def test_strips_arxiv_prefix(self):
        assert _clean_rss_title("arXiv:2401.12345 A Great Paper") == "A Great Paper"

    def test_plain_title_unchanged(self):
        assert _clean_rss_title("A Great Paper") == "A Great Paper"


class TestCleanHtml:
    def test_strips_tags_and_collapses_whitespace(self):
        assert _clean_html("<p>Hello   <b>world</b></p>") == "Hello world"


class TestLatexToUnicode:
    def test_plain_text_unchanged(self):
        assert _latex_to_unicode("Ada Lovelace") == "Ada Lovelace"

    def test_apostrophe_not_treated_as_latex(self):
        # No backslash -> returned as-is (O'Brien must not be mangled).
        assert _latex_to_unicode("O'Brien") == "O'Brien"

    def test_decodes_latex_accents(self):
        out = _latex_to_unicode(r"J\'er\^ome")
        assert "\\" not in out
        assert "é" in out and "ô" in out


class TestParseRssAuthors:
    def test_comma_joined_single_creator(self):
        item = SimpleNamespace(author="Ada Lovelace, Alan Turing")
        assert _parse_rss_authors(item) == ["Ada Lovelace", "Alan Turing"]

    def test_latex_names_decoded(self):
        item = SimpleNamespace(author=r"J\'er\^ome Dupont, Alan Turing")
        authors = _parse_rss_authors(item)
        assert authors[1] == "Alan Turing"
        assert "\\" not in authors[0] and "é" in authors[0]

    def test_authors_list_field(self):
        item = SimpleNamespace(authors=[{"name": "Ada Lovelace"}, {"name": "Alan Turing"}])
        assert _parse_rss_authors(item) == ["Ada Lovelace", "Alan Turing"]

    def test_empty(self):
        assert _parse_rss_authors(SimpleNamespace(author="")) == []


class TestParseRssCategories:
    def test_from_tags(self):
        item = SimpleNamespace(tags=[SimpleNamespace(term="cs.AI"), SimpleNamespace(term="cs.LG")])
        assert _parse_rss_categories(item) == ["cs.AI", "cs.LG"]

    def test_no_tags(self):
        assert _parse_rss_categories(SimpleNamespace(other=1)) == []


class TestAnnouncementWindow:
    # 2024-01-01 is a Monday, so the weekdays below are known.
    def test_friday_has_no_announcement(self):
        assert _get_announcement_window(date(2024, 1, 5)) is None

    def test_saturday_has_no_announcement(self):
        assert _get_announcement_window(date(2024, 1, 6)) is None

    def test_tuesday_is_a_one_day_window(self):
        start, end = _get_announcement_window(date(2024, 1, 2))
        assert end - start == timedelta(days=1)

    def test_sunday_is_a_one_day_window(self):
        start, end = _get_announcement_window(date(2024, 1, 7))
        assert end - start == timedelta(days=1)

    def test_monday_covers_the_weekend(self):
        start, end = _get_announcement_window(date(2024, 1, 8))
        assert end - start == timedelta(days=3)
