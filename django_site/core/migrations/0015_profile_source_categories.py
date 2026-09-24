from django.db import migrations, models


def flat_to_per_source(apps, schema_editor):
    """Every existing selection was an arXiv category — namespace it as one."""
    Profile = apps.get_model("core", "Profile")
    for profile in Profile.objects.all().iterator():
        codes = list(profile.categories or [])
        profile.source_categories = {"arxiv": codes} if codes else {}
        profile.save(update_fields=["source_categories"])


def per_source_to_flat(apps, schema_editor):
    """Flatten back to one list, preserving source order and dropping dupes."""
    Profile = apps.get_model("core", "Profile")
    for profile in Profile.objects.all().iterator():
        raw = profile.source_categories
        codes = []
        if isinstance(raw, dict):
            for source_codes in raw.values():
                for code in source_codes or []:
                    if code not in codes:
                        codes.append(code)
        elif isinstance(raw, list):
            codes = list(raw)
        profile.categories = codes
        profile.save(update_fields=["categories"])


class Migration(migrations.Migration):
    """Store profile categories per source instead of in one flat list.

    Category codes are only unique within a preprint server, so a flat list
    cannot express "cs.AI on arXiv and neuroscience on bioRxiv". The column is
    renamed as well as retyped so that any raw SQL still selecting
    ``categories`` fails loudly rather than silently reading jsonb as text.
    """

    dependencies = [
        ("core", "0014_rename_arxiv_id_to_source_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="source_categories",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(flat_to_per_source, per_source_to_flat),
        migrations.RemoveField(
            model_name="profile",
            name="categories",
        ),
    ]
