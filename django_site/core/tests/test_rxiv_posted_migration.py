"""Tests for migration 0018, which backfills metadata["posted"] on bioRxiv/medRxiv papers."""

from datetime import date, datetime, time
from importlib import import_module
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import TestCase

from core.models import Paper

migration = import_module("core.migrations.0018_backfill_rxiv_posted_dates")
ET = ZoneInfo("America/New_York")


def _et_midnight(y, m, d):
    return datetime.combine(date(y, m, d), time(), ET)


def _paper(source_id, source, submitted_date, metadata=None):
    return Paper.objects.create(
        source_id=source_id,
        title=source_id,
        source=source,
        submitted_date=submitted_date,
        metadata=metadata,
    )


class BackfillRxivPostedTests(TestCase):
    def test_fills_in_the_day_before_submitted_date(self):
        bio = _paper("b", "biorxiv", _et_midnight(2026, 10, 27), {"categories": ["neuroscience"]})
        med = _paper("m", "medrxiv", _et_midnight(2027, 1, 1))
        migration.backfill_posted(apps, None)
        bio.refresh_from_db()
        med.refresh_from_db()
        self.assertEqual(bio.metadata, {"categories": ["neuroscience"], "posted": "2026-10-26"})
        self.assertEqual(med.metadata, {"posted": "2026-12-31"})
        # The stored run-day date is unchanged.
        self.assertEqual(bio.submitted_date, _et_midnight(2026, 10, 27))

    def test_dst_start(self):
        # Stored as the day after posting on 14 Mar 2027, the day DST starts.
        p = _paper("b", "biorxiv", _et_midnight(2027, 3, 15))
        migration.backfill_posted(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.metadata["posted"], "2027-03-14")

    def test_leaves_other_rows_alone(self):
        rows = [
            _paper("a", "arxiv", _et_midnight(2026, 10, 27), {}),
            _paper("b", "biorxiv", _et_midnight(2026, 10, 27), {"posted": "2026-10-26"}),
            _paper("c", "biorxiv", datetime(2026, 10, 27, 12, 0, tzinfo=ET), {}),
            _paper("d", "medrxiv", None, {}),
        ]
        before = [p.metadata for p in rows]
        migration.backfill_posted(apps, None)
        for p, expected in zip(rows, before):
            p.refresh_from_db()
            self.assertEqual(p.metadata, expected)
