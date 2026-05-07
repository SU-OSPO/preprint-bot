"""
Re-fetch metadata (title, abstract, categories, authors) from the arXiv API
for all papers that have a valid arxiv_id.

Usage:
    python manage.py refresh_arxiv_metadata          # dry run
    python manage.py refresh_arxiv_metadata --apply   # actually update
"""

import re
import time

from django.core.management.base import BaseCommand

from core.models import Paper


BATCH_SIZE = 50  # arXiv API supports up to 200, but smaller batches are safer
ARXIV_ID_RE = re.compile(
    r"^(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})$", re.IGNORECASE
)


def _fetch_batch(arxiv_ids):
    """Fetch metadata for a batch of arXiv IDs. Returns dict keyed by bare ID."""
    try:
        import arxiv as arxiv_lib
    except ImportError:
        raise ImportError("Install the arxiv package: pip install arxiv")

    client = arxiv_lib.Client()
    search = arxiv_lib.Search(id_list=arxiv_ids)
    results = {}
    for paper in client.results(search):
        aid = paper.get_short_id().split("v")[0]  # strip version
        results[aid] = {
            "title": paper.title,
            "abstract": paper.summary,
            "authors": [a.name for a in paper.authors],
            "categories": list(paper.categories),
        }
    return results


class Command(BaseCommand):
    help = "Re-fetch titles, abstracts, and categories from arXiv for papers with arxiv_ids."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually update the database. Without this flag, only a dry run is performed.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]

        # Only include papers with valid arXiv IDs (skip legacy citation-style IDs)
        papers = [
            p for p in Paper.objects.filter(arxiv_id__isnull=False)
            .exclude(arxiv_id="")
            .order_by("id")
            if ARXIV_ID_RE.match(re.sub(r"v\d+$", "", p.arxiv_id))
        ]

        if not papers:
            self.stdout.write(self.style.SUCCESS("No papers with valid arXiv IDs found."))
            return

        self.stdout.write(f"Found {len(papers)} paper(s) with valid arXiv IDs.")

        batches = [papers[i:i + BATCH_SIZE] for i in range(0, len(papers), BATCH_SIZE)]

        updated = 0
        skipped = 0
        failed = 0

        for batch_num, batch in enumerate(batches, 1):
            self.stdout.write(f"\nBatch {batch_num}/{len(batches)} ({len(batch)} papers)...")

            id_map = {p.arxiv_id: p for p in batch}
            arxiv_ids = list(id_map.keys())

            try:
                metadata = _fetch_batch(arxiv_ids)
            except Exception as e:
                self.stderr.write(f"  Batch failed: {e}")
                failed += len(batch)
                continue

            for aid, paper in id_map.items():
                # _fetch_batch strips version suffixes from keys
                bare_aid = re.sub(r"v\d+$", "", aid)
                meta = metadata.get(bare_aid) or metadata.get(aid)
                if not meta:
                    self.stdout.write(f"  {aid}: not found on arXiv")
                    skipped += 1
                    continue

                changes = []
                if meta["title"] and meta["title"] != paper.title:
                    changes.append(
                        f"title: {paper.title[:40]}... -> {meta['title'][:40]}..."
                    )
                if meta["abstract"] and meta["abstract"] != paper.abstract:
                    changes.append("abstract updated")

                # Merge categories and authors into existing metadata
                new_metadata = paper.metadata or {}
                if isinstance(new_metadata, str):
                    import json
                    try:
                        new_metadata = json.loads(new_metadata)
                    except Exception:
                        new_metadata = {}
                if meta["categories"] and meta["categories"] != new_metadata.get("categories", []):
                    new_metadata["categories"] = meta["categories"]
                    changes.append(f"categories: {meta['categories']}")
                if meta["authors"] and meta["authors"] != new_metadata.get("authors", []):
                    new_metadata["authors"] = meta["authors"]
                    changes.append("authors updated")

                if not changes:
                    skipped += 1
                    continue

                if apply:
                    paper.title = meta["title"] or paper.title
                    paper.abstract = meta["abstract"] or paper.abstract
                    paper.metadata = new_metadata
                    paper.save(update_fields=["title", "abstract", "metadata"])

                mark = "+" if apply else "~"
                self.stdout.write(f"  {mark} {aid}: {', '.join(changes)}")
                updated += 1

            # Respect arXiv rate limits between batches
            if batch_num < len(batches):
                self.stdout.write("  Waiting 3s for rate limit...")
                time.sleep(3)

        self.stdout.write("")
        if apply:
            self.stdout.write(self.style.SUCCESS(
                f"Updated {updated} paper(s). Skipped {skipped}. Failed {failed}."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Dry run: would update {updated} paper(s). Skipped {skipped}. Failed {failed}. "
                f"Run with --apply to execute."
            ))
