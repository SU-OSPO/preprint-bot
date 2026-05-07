"""
Add sent_in_email boolean to recommendations table for digest rollup,
and add index on sent_in_email. Existing recommendations are backfilled
as already sent so the first digest after deployment doesn't re-send
everything.
"""

from django.db import migrations, models


def backfill_sent_in_email(apps, schema_editor):
    """Mark all existing recommendations as already sent."""
    Recommendation = apps.get_model("core", "Recommendation")
    Recommendation.objects.all().update(sent_in_email=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_alter_paper_corpus_alter_pbuser_password_and_more"),
    ]

    operations = [
        # Add sent_in_email boolean to Recommendation
        migrations.AddField(
            model_name="recommendation",
            name="sent_in_email",
            field=models.BooleanField(default=False),
        ),
        # Backfill existing recommendations as already sent
        migrations.RunPython(backfill_sent_in_email, migrations.RunPython.noop),
        # Index for fast unsent-recommendation queries
        migrations.AddIndex(
            model_name="recommendation",
            index=models.Index(fields=["sent_in_email"], name="recommendations_sent_idx"),
        ),
    ]
