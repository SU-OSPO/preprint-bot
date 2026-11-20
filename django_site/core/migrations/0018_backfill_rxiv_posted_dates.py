"""
Record the posting day of existing bioRxiv/medRxiv papers in metadata["posted"].

The pipeline dates these papers at midnight Eastern Time on the day *after*
posting, to line up with arXiv papers from the same run, and now also keeps
the server's own posting date as ``metadata["posted"]``. Rows stored before
that have no ``posted`` key, so the web app would show the shifted day as the
posting date. This fills it in as the day before ``submitted_date``.

Scope guards:
  * Rows that already have ``posted`` are left alone.
  * Only rows at exactly midnight Eastern Time are filled in, the only shape
    the pipeline ever wrote for these sources.
  * ``submitted_date`` itself is not changed.
"""

from datetime import time, timedelta
from zoneinfo import ZoneInfo

from django.db import migrations

_EASTERN = ZoneInfo("America/New_York")
_SOURCES = ("biorxiv", "medrxiv")


def backfill_posted(apps, schema_editor):
    Paper = apps.get_model("core", "Paper")
    rows = Paper.objects.filter(source__in=_SOURCES, submitted_date__isnull=False)
    for paper in rows.only("id", "metadata", "submitted_date").iterator():
        metadata = paper.metadata if isinstance(paper.metadata, dict) else {}
        if metadata.get("posted"):
            continue
        local = paper.submitted_date.astimezone(_EASTERN)
        if local.time() != time():
            continue
        metadata["posted"] = (local.date() - timedelta(days=1)).isoformat()
        Paper.objects.filter(pk=paper.pk).update(metadata=metadata)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_alter_paper_source"),
    ]

    operations = [
        # The added key is harmless to keep, so reversing leaves it in place.
        migrations.RunPython(backfill_posted, migrations.RunPython.noop),
    ]
