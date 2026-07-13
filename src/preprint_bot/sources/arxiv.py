"""
arXiv preprint source.

Primary method: RSS feed (contains exactly the latest announcement).
Fallback: arXiv search API with submission-window calculation (for
backfilling historical dates).
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import List
from zoneinfo import ZoneInfo

import feedparser
import httpx

from .base import PaperEntry, PreprintSource
from ..config import USER_AGENT

_RSS_BASE = "https://rss.arxiv.org/rss"
_API_BASE = "https://export.arxiv.org/api/query"


class ArxivSource(PreprintSource):
    """Fetch new papers from arXiv via RSS or the search API."""

    @property
    def name(self) -> str:
        return "arxiv"

    # ── RSS (primary) ──────────────────────────────────────────────

    async def fetch_latest(
        self, categories: List[str]
    ) -> List[PaperEntry]:
        """Fetch the current announcement via the arXiv RSS feed.

        The RSS feed is updated daily at midnight EST and contains
        exactly the papers from the most recent announcement.  We
        filter for ``announce_type == 'new'`` to skip replacements
        and cross-listings.
        """
        # Combine categories with '+' to fetch a single merged feed
        cat_str = "+".join(categories)
        url = f"{_RSS_BASE}/{cat_str}"

        print(f"\nFetching latest arXiv papers via RSS")
        print(f"  Feed: {url}")
        print(f"  Categories: {categories}")

        async with httpx.AsyncClient(
            timeout=30, headers={"User-Agent": USER_AGENT}
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()

        for item in feed.entries:
            # Only new submissions (skip replace, cross, replace-cross)
            announce_type = getattr(item, "arxiv_announce_type", "new")
            if announce_type != "new":
                continue

            arxiv_id = _extract_arxiv_id(item.link)
            if not arxiv_id or arxiv_id in seen_ids:
                continue
            seen_ids.add(arxiv_id)

            entries.append(
                PaperEntry(
                    source_id=arxiv_id,
                    title=_clean_rss_title(item.title),
                    abstract=_clean_html(
                        getattr(item, "description", "")
                        or getattr(item, "summary", "")
                    ),
                    url=item.link,
                    pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    authors=_parse_rss_authors(item),
                    categories=_parse_rss_categories(item),
                    published=getattr(item, "published", ""),
                    source="arxiv",
                    metadata={
                        "arxiv_url": item.link,
                        "announce_type": announce_type,
                    },
                )
            )

        print(f"  Found {len(entries)} new papers")
        return entries

    # ── API with submission windows (backfill) ─────────────────────

    async def fetch_by_date(
        self,
        target_date,
        categories: List[str],
    ) -> List[PaperEntry]:
        """Fetch papers for a specific date using the arXiv search API.

        Uses ``_get_announcement_window`` to map the target date to the
        correct submission window, then queries ``submittedDate``.
        """
        window = _get_announcement_window(target_date)
        if window is None:
            print(
                f"\nNo arXiv announcement on "
                f"{target_date.strftime('%A %Y-%m-%d')} — skipping fetch."
            )
            return []

        start_dt, end_dt = window
        start = start_dt.strftime("%Y%m%d%H%M")
        end = end_dt.strftime("%Y%m%d%H%M")

        print(
            f"\nFetching arXiv papers via API for "
            f"{target_date.strftime('%A %Y-%m-%d')}"
        )
        print(f"  Submission window: {start_dt} → {end_dt} (UTC)")
        print(f"  Categories: {categories}")

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(
            timeout=30, headers={"User-Agent": USER_AGENT}
        ) as client:
            # Combine all categories into a single OR query to avoid
            # per-category rate limiting (26 categories = 26 requests)
            cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
            query = f"({cat_query})+AND+submittedDate:[{start}+TO+{end}]"

            papers = await _api_fetch_all(client, query)
            for item in papers:
                arxiv_id = item.id.split("/")[-1]
                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                entries.append(
                    PaperEntry(
                        source_id=arxiv_id,
                        title=item.title.strip(),
                        abstract=item.summary.strip(),
                        url=item.id,
                        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                        authors=[
                            a.name
                            for a in getattr(item, "authors", [])
                        ],
                        categories=[
                            tag.term
                            for tag in getattr(item, "tags", [])
                        ],
                        published=getattr(item, "published", ""),
                        source="arxiv",
                        metadata={"arxiv_url": item.id},
                    )
                )

        print(f"  Total: {len(entries)} new papers")
        return entries


# ── Helpers ────────────────────────────────────────────────────────


def _extract_arxiv_id(link: str) -> str | None:
    """Pull the arXiv ID from an abstract URL, stripping any version."""
    m = re.search(r"abs/([^\s?#]+)", link or "")
    if not m:
        return None
    raw = m.group(1)
    return re.sub(r"v\d+$", "", raw)  # strip version suffix


def _clean_rss_title(raw: str) -> str:
    """Remove the 'arXiv:2401.12345' prefix that the RSS feed prepends."""
    return re.sub(r"^arXiv:\S+\s*", "", raw).strip()


def _clean_html(text: str) -> str:
    """Strip HTML tags from RSS description fields."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_rss_authors(item) -> List[str]:
    """Extract author list from an RSS item.

    arXiv's RSS puts all authors in a single ``<dc:creator>`` element
    as one comma-separated string.
    """
    # Gather raw name strings from whichever field feedparser populated
    raw: List[str] = []
    if hasattr(item, "authors") and item.authors:
        raw = [a.get("name", "") for a in item.authors if a.get("name")]
    if not raw:
        author_str = getattr(item, "author", "")
        if author_str:
            raw = [author_str]

    # Split any comma-joined entries into individual authors
    names: List[str] = []
    for entry in raw:
        names.extend(a.strip() for a in entry.split(",") if a.strip())
    return names


def _parse_rss_categories(item) -> List[str]:
    """Extract category list from an RSS item."""
    if hasattr(item, "tags") and item.tags:
        return [tag.term for tag in item.tags if hasattr(tag, "term")]
    return []


async def _api_fetch_all(
    client: httpx.AsyncClient,
    query: str,
    page_size: int = 500,
) -> list:
    """Fetch all results for a query, paginating as needed.

    The arXiv API caps ``max_results`` at ~30 000, but practical
    pages should be ≤ 500 to avoid timeouts.  We read
    ``opensearch:totalResults`` from the first page to know how
    many pages to fetch.
    """
    all_entries: list = []
    offset = 0
    total: int | None = None  # learned from first response

    while True:
        url = (
            f"{_API_BASE}?search_query={query}"
            f"&start={offset}&max_results={page_size}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )
        result = await _api_fetch_page(client, url)

        if result is None:
            break  # retries exhausted

        feed_entries, feed_total = result
        all_entries.extend(feed_entries)

        # Learn total from first response
        if total is None:
            total = feed_total
            if total is not None and total > page_size:
                print(f"  {total} total results, paginating...")

        # Stop if we got fewer than a full page or we've fetched everything
        if len(feed_entries) < page_size:
            break
        if total is not None and len(all_entries) >= total:
            break

        offset += page_size
        await asyncio.sleep(5)  # polite delay between pages

    print(f"  Fetched {len(all_entries)} papers via API")
    return all_entries


async def _api_fetch_page(
    client: httpx.AsyncClient,
    url: str,
    max_retries: int = 4,
    backoff: int = 10,
) -> tuple[list, int | None] | None:
    """Fetch a single page from the arXiv API with retry + rate-limit handling.

    Returns ``(entries, total_results)`` or ``None`` if all retries fail.
    """
    for attempt in range(max_retries):
        try:
            resp = await client.get(url)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = (
                    int(retry_after)
                    if retry_after
                    else backoff * (2**attempt)
                )
                print(
                    f"  429 rate limited, waiting {wait}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            total = int(
                feed.feed.get("opensearch_totalresults", 0)
            ) or None
            return feed.entries, total
        except Exception as e:
            wait = backoff * (2**attempt)
            print(
                f"  API error (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)

    print(f"  API fetch failed after {max_retries} attempts")
    return None


def _get_announcement_window(target_date):
    """Map a calendar date to its arXiv submission window.

    arXiv announces new papers Sunday–Thursday at 20:00 ET.  Each
    announcement covers a specific submission window:

        Submissions received (ET)          Announced (ET)
        ─────────────────────────          ──────────────
        Monday 14:00 – Tuesday 14:00       Tuesday 20:00
        Tuesday 14:00 – Wednesday 14:00    Wednesday 20:00
        Wednesday 14:00 – Thursday 14:00   Thursday 20:00
        Thursday 14:00 – Friday 14:00      Sunday 20:00
        Friday 14:00 – Monday 14:00        Monday 20:00

    Returns ``(start_utc, end_utc)`` or ``None`` for days with no
    announcement (Friday / Saturday).
    """
    eastern = ZoneInfo("America/New_York")
    dow = target_date.weekday()  # 0=Mon … 6=Sun

    if dow in (4, 5):  # Friday or Saturday — no announcement
        return None

    if dow == 6:  # Sunday: covers Thu 14:00 → Fri 14:00
        end_day = target_date - timedelta(days=2)  # Friday
        start_day = target_date - timedelta(days=3)  # Thursday
    elif dow == 0:  # Monday: covers Fri 14:00 → Mon 14:00
        end_day = target_date  # Monday
        start_day = target_date - timedelta(days=3)  # Friday
    else:  # Tue–Thu: previous day 14:00 → current day 14:00
        end_day = target_date
        start_day = target_date - timedelta(days=1)

    start_dt = datetime(
        year=start_day.year,
        month=start_day.month,
        day=start_day.day,
        hour=14, minute=0, second=0,
        tzinfo=eastern,
    )
    end_dt = datetime(
        year=end_day.year,
        month=end_day.month,
        day=end_day.day,
        hour=14, minute=0, second=0,
        tzinfo=eastern,
    )
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc)
