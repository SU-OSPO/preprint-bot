"""
Recover arXiv IDs for papers that have titles but missing arxiv_id values,
by searching the arXiv API by title.

Usage:
    python manage.py recover_arxiv_ids          # dry run
    python manage.py recover_arxiv_ids --apply  # actually update
"""

import re
import time

from django.core.management.base import BaseCommand

from core.models import Paper


ARXIV_ID_RE = re.compile(
    r"^(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})$", re.IGNORECASE
)


def _search_arxiv_by_title(title):
    """Search arXiv for a paper by exact title. Returns (arxiv_id, api_title) or (None, None)."""
    try:
        import arxiv as arxiv_lib
    except ImportError:
        raise ImportError("Install the arxiv package: pip install arxiv")

    # Strip HTML tags and double quotes from title
    clean_title = re.sub(r"<[^>]+>", "", title).strip()
    clean_title = clean_title.replace('"', '')

    client = arxiv_lib.Client()
    search = arxiv_lib.Search(
        query=f'ti:"{clean_title}"',
        max_results=3,
        sort_by=arxiv_lib.SortCriterion.Relevance,
    )

    for result in client.results(search):
        aid = result.get_short_id().split("v")[0]  # strip version
        # Verify it's a valid arXiv ID
        if not ARXIV_ID_RE.match(aid):
            continue
        # Check title similarity (case-insensitive, strip whitespace)
        api_title = re.sub(r"\s+", " ", result.title).strip()
        db_title = re.sub(r"\s+", " ", clean_title).strip()
        if api_title.lower() == db_title.lower():
            return aid, api_title

    return None, None


class Command(BaseCommand):
    help = "Recover arXiv IDs by searching arXiv API by title for papers with missing arxiv_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually update the database. Without this flag, only a dry run is performed.",
        )
        parser.add_argument(
            "--source",
            default="arxiv",
            help="Only process papers with this source value (default: arxiv).",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        source = options["source"]

        papers = list(
            Paper.objects.filter(
                arxiv_id__isnull=True,
                source=source,
            )
            .exclude(title="")
            .order_by("id")
        )

        if not papers:
            self.stdout.write(self.style.SUCCESS("No papers with missing arXiv IDs found."))
            return

        self.stdout.write(f"Found {len(papers)} paper(s) with missing arXiv IDs (source={source}).\n")

        recovered = 0
        not_found = 0
        failed = 0

        for i, paper in enumerate(papers):
            # Respect arXiv rate limits: 3 seconds between requests
            if i > 0:
                time.sleep(3)

            self.stdout.write(f"  [{i + 1}/{len(papers)}] {paper.title[:70]}...")

            try:
                aid, api_title = _search_arxiv_by_title(paper.title)
            except Exception as e:
                self.stderr.write(f"    Error: {e}")
                failed += 1
                continue

            if aid:
                if apply:
                    paper.arxiv_id = aid
                    paper.save(update_fields=["arxiv_id"])
                mark = "+" if apply else "~"
                self.stdout.write(self.style.SUCCESS(f"    {mark} Found: {aid}"))
                recovered += 1
            else:
                self.stdout.write(self.style.WARNING(f"    ? Not found on arXiv"))
                not_found += 1

        self.stdout.write("")
        if apply:
            self.stdout.write(self.style.SUCCESS(
                f"Recovered {recovered} arXiv ID(s). Not found: {not_found}. Failed: {failed}."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Dry run: would recover {recovered} arXiv ID(s). Not found: {not_found}. Failed: {failed}. "
                f"Run with --apply to execute."
            ))
