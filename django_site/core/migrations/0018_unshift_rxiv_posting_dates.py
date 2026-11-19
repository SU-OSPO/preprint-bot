"""
Move bioRxiv/medRxiv paper dates back to the day each paper was posted.

The pipeline used to store these papers at midnight Eastern Time on the day
*after* posting, so they grouped with the arXiv papers from the same nightly
run. Recommendations are now grouped by when they were received, so the
paper date is shown as-is and must be the real posting day.

Scope guard: only rows at exactly midnight Eastern Time are shifted, the
only shape the pipeline ever wrote for these sources.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import migrations

_EASTERN = ZoneInfo("America/New_York")
_SOURCES = ("biorxiv", "medrxiv")


def _shift(apps, days):
    """Move each affected paper's date by *days* calendar days in Eastern Time."""
    Paper = apps.get_model("core", "Paper")
    rows = Paper.objects.filter(source__in=_SOURCES, submitted_date__isnull=False)
    for paper in rows.only("id", "submitted_date").iterator():
        local = paper.submitted_date.astimezone(_EASTERN)
        if local.time() != time():
            continue
        # Recombine at midnight so a DST change can't move the time of day.
        new = datetime.combine(local.date() + timedelta(days=days), time(), _EASTERN)
        Paper.objects.filter(pk=paper.pk).update(submitted_date=new)


def unshift(apps, schema_editor):
    _shift(apps, -1)


def reshift(apps, schema_editor):
    _shift(apps, 1)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_alter_paper_source"),
    ]

    operations = [
        migrations.RunPython(unshift, reshift),
    ]
