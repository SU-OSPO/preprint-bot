# Generated for preprint-bot v1.1
# Enforce one recommendation per (profile, paper) to prevent duplicate
# digest emails when the pipeline is re-run for the same profile.

from django.db import migrations, models


def backfill_profile_and_dedupe(apps, schema_editor):
    """Backfill recommendations.profile_id from the parent run, then dedupe
    so each (profile, paper) pair has exactly one row.

    Dedupe rule: keep the row with the highest run_id (most recent run).
    Before deleting, OR-propagate ``sent_in_email`` across all duplicates
    onto the kept row so a paper that was already emailed in *any*
    duplicate stays marked as sent and isn't re-emailed.

    Recommendations whose parent run has a NULL profile_id are orphaned
    under the new model (a recommendation must belong to a profile);
    those are deleted outright.
    """
    with schema_editor.connection.cursor() as cur:
        # 1. Backfill profile_id from the parent recommendation_run.
        cur.execute(
            """
            UPDATE recommendations r
            SET profile_id = rr.profile_id
            FROM recommendation_runs rr
            WHERE r.run_id = rr.id
              AND r.profile_id IS NULL
            """
        )

        # 2. Drop orphans: recommendations whose run has no profile.
        # These can't satisfy the new (profile, paper) constraint.
        cur.execute(
            "DELETE FROM recommendations WHERE profile_id IS NULL"
        )

        # 3. For each duplicated (profile, paper), propagate sent_in_email
        # onto the row we're going to keep (the one with the highest run_id).
        cur.execute(
            """
            WITH agg AS (
                SELECT profile_id,
                       paper_id,
                       BOOL_OR(sent_in_email) AS any_sent,
                       MAX(run_id)            AS keep_run_id
                FROM recommendations
                GROUP BY profile_id, paper_id
                HAVING COUNT(*) > 1
            )
            UPDATE recommendations r
            SET sent_in_email = agg.any_sent
            FROM agg
            WHERE r.profile_id = agg.profile_id
              AND r.paper_id   = agg.paper_id
              AND r.run_id     = agg.keep_run_id
            """
        )

        # 4. Delete the duplicate losers (everything except the highest run_id
        # row in each (profile, paper) group). profile_recommendations rows
        # cascade automatically via the FK.
        cur.execute(
            """
            DELETE FROM recommendations r
            USING (
                SELECT profile_id, paper_id, MAX(run_id) AS keep_run_id
                FROM recommendations
                GROUP BY profile_id, paper_id
            ) keepers
            WHERE r.profile_id = keepers.profile_id
              AND r.paper_id   = keepers.paper_id
              AND r.run_id    <> keepers.keep_run_id
            """
        )


def reverse_backfill(apps, schema_editor):
    """Cannot reverse — deduped duplicates and orphans are gone for good."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_merge_20260508_1148"),
    ]

    operations = [
        # Step 1: add the FK as nullable so we can populate it before
        # enforcing NOT NULL.
        migrations.AddField(
            model_name="recommendation",
            name="profile",
            field=models.ForeignKey(
                to="core.profile",
                on_delete=models.deletion.CASCADE,
                related_name="recommendations",
                blank=True,
                null=True,
            ),
        ),
        # Step 2: backfill, drop orphans, and dedupe.
        migrations.RunPython(backfill_profile_and_dedupe, reverse_backfill),
        # Step 3: every surviving row has a profile, so make the FK required.
        migrations.AlterField(
            model_name="recommendation",
            name="profile",
            field=models.ForeignKey(
                to="core.profile",
                on_delete=models.deletion.CASCADE,
                related_name="recommendations",
            ),
        ),
        # Step 4: enforce one recommendation per (profile, paper).
        # The existing (run, paper) constraint is preserved as a redundant
        # but cheap intra-run invariant.
        migrations.AlterUniqueTogether(
            name="recommendation",
            unique_together={("run", "paper"), ("profile", "paper")},
        ),
    ]
