from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename the Paper.arxiv_id field (and its index) to source_id."""

    dependencies = [
        ("core", "0013_decode_latex_author_names"),
    ]

    operations = [
        migrations.RenameField(
            model_name="paper",
            old_name="arxiv_id",
            new_name="source_id",
        ),
        migrations.RemoveIndex(
            model_name="paper",
            name="papers_arxiv_id_idx",
        ),
        migrations.AddIndex(
            model_name="paper",
            index=models.Index(fields=["source_id"], name="papers_source_id_idx"),
        ),
    ]
