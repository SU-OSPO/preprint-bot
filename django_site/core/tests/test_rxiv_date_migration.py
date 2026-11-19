"""Tests for migration 0018, which moves bioRxiv/medRxiv dates back to the posting day."""

from datetime import datetime, time
from importlib import import_module
from zoneinfo import ZoneInfo

from django.apps import apps
from django.test import TestCase

from core.models import Paper

migration = import_module("core.migrations.0018_unshift_rxiv_posting_dates")
ET = ZoneInfo("America/New_York")


def _et_midnight(y, m, d):
    return datetime.combine(datetime(y, m, d).date(), time(), ET)


def _paper(source_id, source, submitted_date):
    return Paper.objects.create(
        source_id=source_id, title=source_id, source=source, submitted_date=submitted_date
    )


class UnshiftRxivDatesTests(TestCase):
    def test_moves_rxiv_dates_back_one_day(self):
        bio = _paper("b", "biorxiv", _et_midnight(2026, 10, 27))
        med = _paper("m", "medrxiv", _et_midnight(2027, 1, 1))
        migration.unshift(apps, None)
        bio.refresh_from_db()
        med.refresh_from_db()
        self.assertEqual(bio.submitted_date, _et_midnight(2026, 10, 26))
        self.assertEqual(med.submitted_date, _et_midnight(2026, 12, 31))

    def test_stays_at_eastern_midnight_across_dst(self):
        # Stored as the day after posting on 14 Mar 2027, the day DST starts.
        p = _paper("b", "biorxiv", _et_midnight(2027, 3, 15))
        migration.unshift(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.submitted_date, _et_midnight(2027, 3, 14))

    def test_leaves_other_rows_alone(self):
        arxiv = _paper("a", "arxiv", _et_midnight(2026, 10, 27))
        not_midnight = _paper("b", "biorxiv", datetime(2026, 10, 27, 12, 0, tzinfo=ET))
        undated = _paper("c", "medrxiv", None)
        migration.unshift(apps, None)
        for p, expected in (
            (arxiv, _et_midnight(2026, 10, 27)),
            (not_midnight, datetime(2026, 10, 27, 12, 0, tzinfo=ET)),
            (undated, None),
        ):
            p.refresh_from_db()
            self.assertEqual(p.submitted_date, expected)

    def test_reverse_restores_original(self):
        p = _paper("b", "biorxiv", _et_midnight(2026, 10, 27))
        migration.unshift(apps, None)
        migration.reshift(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.submitted_date, _et_midnight(2026, 10, 27))
