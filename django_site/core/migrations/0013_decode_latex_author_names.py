r"""
Decode LaTeX author names in papers.metadata to Unicode.

arXiv's RSS feed encodes author names in LaTeX (e.g. ``J\'er\^ome`` for
``Jérôme``). This migration converts existing RSS-ingested author names
to Unicode, matching what the corrected pipeline now produces.

Scope guards:
  * Only RSS-ingested rows are touched (they carry ``announce_type`` in
    metadata). API-path rows are already Unicode and are left alone.
  * Only names containing a backslash are converted, so clean Unicode names
    and apostrophes such as ``O'Brien`` are never altered.
"""

from django.db import migrations


def _decode_name(text, converter):
    """Convert a single LaTeX-encoded name to Unicode; leave clean names as-is."""
    if not isinstance(text, str) or "\\" not in text:
        return text
    try:
        return converter.latex_to_text(text).strip()
    except Exception:
        return text


def decode_latex_authors(apps, schema_editor):
    """Rewrite affected metadata["authors"] in place."""
    from pylatexenc.latex2text import LatexNodes2Text

    Paper = apps.get_model("core", "Paper")
    converter = LatexNodes2Text()

    fixed = 0
    # iterator() keeps memory flat over a large papers table.
    for paper in Paper.objects.only("id", "metadata").iterator():
        metadata = paper.metadata
        if not isinstance(metadata, dict):
            continue
        # Only RSS-ingested rows carry announce_type (and LaTeX names).
        if "announce_type" not in metadata:
            continue
        authors = metadata.get("authors")
        if not isinstance(authors, list) or not authors:
            continue

        new_authors = [_decode_name(a, converter) for a in authors]
        if new_authors == authors:
            continue

        metadata["authors"] = new_authors
        paper.metadata = metadata
        paper.save(update_fields=["metadata"])
        fixed += 1

    if fixed:
        print(f"  Decoded LaTeX author names for {fixed} paper(s).")
    else:
        print("  No affected rows found.")


def reverse_noop(apps, schema_editor):
    """Unicode names are always preferable; no reason to revert."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_split_author_lists"),
    ]

    operations = [
        migrations.RunPython(decode_latex_authors, reverse_noop),
    ]
