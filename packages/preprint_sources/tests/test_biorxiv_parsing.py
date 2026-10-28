"""Unit tests for the pure bioRxiv helpers: the Eastern date and record conversion."""

from datetime import date, datetime, timezone

from preprint_sources.base import PaperEntry
from preprint_sources.biorxiv import _entry_from_item, _yesterday_et

DOI = "10.64898/2026.10.25.761658"


def _item(**overrides):
    """An API record shaped like the real ones (values made up)."""
    item = {
        "doi": DOI,
        "title": " A Title ",
        "authors": "Ji, Z.; Zhang, H.",
        "date": "2026-10-26",
        "version": "1",
        "type": "new results",
        "license": "cc_by",
        "category": "neuroscience",
        "abstract": "Body.",
        "published": "NA",
        "server": "bioRxiv",
    }
    item.update(overrides)
    return item


def test_yesterday_et_uses_eastern_time():
    # 02:00 UTC on Oct 28 is still the evening of Oct 27 in New York.
    late_evening_et = datetime(2026, 10, 28, 2, 0, tzinfo=timezone.utc)
    assert _yesterday_et(late_evening_et) == date(2026, 10, 26)
    afternoon_et = datetime(2026, 10, 28, 15, 0, tzinfo=timezone.utc)
    assert _yesterday_et(afternoon_et) == date(2026, 10, 27)


def test_entry_from_first_version():
    assert _entry_from_item(_item()) == PaperEntry(
        source_id=DOI,
        title="A Title",
        abstract="Body.",
        url=f"https://www.biorxiv.org/content/{DOI}",
        pdf_url=f"https://www.biorxiv.org/content/{DOI}v1.full.pdf",
        authors=["Ji, Z.", "Zhang, H."],
        categories=["neuroscience"],
        published="2026-10-26",
        source="biorxiv",
    )


def test_entry_accepts_integer_version():
    # The API sends "1" today; an integer 1 must not be dropped as a revision.
    assert _entry_from_item(_item(version=1)) is not None


def test_revision_is_skipped():
    assert _entry_from_item(_item(version="2")) is None
