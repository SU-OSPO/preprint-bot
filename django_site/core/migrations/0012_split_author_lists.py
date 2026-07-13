"""
Split comma-joined author strings in papers.metadata into proper lists.

arXiv's RSS feed delivers all authors in a single ``<dc:creator>`` element
as one comma-separated string. Before the fix to ``_parse_rss_authors``,
feedparser's one-element ``item.authors`` list was stored verbatim, so
affected papers have::

    metadata["authors"] == ["Alice Smith, Bob Jones, Carol Lee"]   (1 element)

instead of::

    metadata["authors"] == ["Alice Smith", "Bob Jones", "Carol Lee"]

This migration finds those rows and splits the single string into a proper
list, matching what the corrected pipeline now produces. Papers fetched via
the arXiv API path (which always produced correct lists) are left alone.
"""

from django.db import migrations


def _needs_split(authors):
    """True if ``authors`` is a single comma-joined string in a 1-element list."""
    return (
        isinstance(authors, list)
        and len(authors) == 1
        and isinstance(authors[0], str)
        and "," in authors[0]
    )


def split_author_lists(apps, schema_editor):
    """Rewrite affected metadata["authors"] in place."""
    Paper = apps.get_model("core", "Paper")

    fixed = 0
    # iterator() keeps memory flat over a large papers table.
    for paper in Paper.objects.iterator():
        metadata = paper.metadata
        if not isinstance(metadata, dict):
            continue
        # Only touch RSS-ingested rows (they carry announce_type). API-path
        # rows are left alone.
        if "announce_type" not in metadata:
            continue
        authors = metadata.get("authors")
        if not _needs_split(authors):
            continue

        new_authors = [a.strip() for a in authors[0].split(",") if a.strip()]
        # Only a fix if the split actually yields more than one name.
        if len(new_authors) <= 1:
            continue

        metadata["authors"] = new_authors
        paper.metadata = metadata
        paper.save(update_fields=["metadata"])
        fixed += 1

    if fixed:
        print(f"  Split author lists for {fixed} paper(s).")
    else:
        print("  No affected rows found.")


def reverse_noop(apps, schema_editor):
    """Split authors are always better; no reason to revert."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_recommendation_profile_id"),
    ]

    operations = [
        migrations.RunPython(split_author_lists, reverse_noop),
    ]
