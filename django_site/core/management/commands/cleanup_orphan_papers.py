"""
Remove Paper rows that are no longer linked to any corpus, and delete
their PDF files from disk.

Usage:
    python manage.py cleanup_orphan_papers        # dry run
    python manage.py cleanup_orphan_papers --apply # actually delete
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import Paper


class Command(BaseCommand):
    help = "Delete papers not linked to any corpus (and their PDF files)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete orphaned papers. Without this flag, only a dry run is performed.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]

        # Find papers with zero M2M corpus links
        orphans = Paper.objects.filter(corpora__isnull=True).distinct()

        count = orphans.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned papers found."))
            return

        self.stdout.write(f"Found {count} orphaned paper(s).")

        deleted_files = 0
        deleted_rows = 0
        for paper in orphans.iterator():
            if paper.pdf_path:
                pdf_path = Path(paper.pdf_path)
                if pdf_path.exists():
                    if apply:
                        try:
                            pdf_path.unlink()
                            deleted_files += 1
                        except OSError as e:
                            self.stderr.write(f"  Could not delete {pdf_path}: {e}")
                    else:
                        self.stdout.write(f"  Would delete: {pdf_path}")
                        deleted_files += 1

            if apply:
                paper.delete()
                deleted_rows += 1
            else:
                self.stdout.write(f"  Would remove Paper pk={paper.pk}: {paper.title[:60]}")
                deleted_rows += 1

        if apply:
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted_rows} paper(s) and {deleted_files} file(s)."))
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would delete {deleted_rows} paper(s) and {deleted_files} file(s). "
                    f"Run with --apply to execute."
                )
            )
