"""Unit tests for the pure medRxiv helpers: the Eastern date and record conversion."""

from datetime import date, datetime, timezone

from preprint_sources.base import PaperEntry
from preprint_sources.rxiv import _entry_from_item, _yesterday_et

DOI = "10.64898/2026.10.25.26312345"


def _item(**overrides):
    """An API record shaped like the real ones (values made up)."""
    item = {
        "doi": DOI,
        "title": " A Title ",
        "authors": "Ji, Z.; Zhang, H.",
        "date": "2026-10-26",
        "version": "1",
        "license": "cc_by",
        "category": "epidemiology",
        "abstract": "Body.",
        "published": "NA",
        "server": "medRxiv",
    }
    item.update(overrides)
    return item


def test_yesterday_et_uses_eastern_time():
    late_evening_et = datetime(2026, 10, 28, 2, 0, tzinfo=timezone.utc)
    assert _yesterday_et(late_evening_et) == date(2026, 10, 26)
    afternoon_et = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
    assert _yesterday_et(afternoon_et) == date(2026, 10, 27)


def test_entry_from_first_version():
    assert _entry_from_item(_item(), "https://www.medrxiv.org", "medrxiv") == PaperEntry(
        source_id=DOI,
        title="A Title",
        abstract="Body.",
        url=f"https://www.medrxiv.org/content/{DOI}",
        pdf_url=f"https://www.medrxiv.org/content/{DOI}v1.full.pdf",
        authors=["Ji, Z.", "Zhang, H."],
        categories=["epidemiology"],
        published="2026-10-27T00:00:00-04:00",
        source="medrxiv",
    )


def test_published_rolls_into_next_year_at_eastern_midnight():
    entry = _entry_from_item(_item(date="2026-12-31"), "https://www.medrxiv.org", "medrxiv")
    assert entry.published == "2027-01-01T00:00:00-05:00"


def test_entry_accepts_integer_version():
    assert _entry_from_item(_item(version=1), "https://www.medrxiv.org", "medrxiv") is not None


def test_revision_is_skipped():
    assert _entry_from_item(_item(version="2"), "https://www.medrxiv.org", "medrxiv") is None
