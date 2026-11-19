from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from .base import PaperEntry, PreprintSource
from .settings import USER_AGENT

_API_ROOT = "https://api.biorxiv.org/details"
_EASTERN = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


class RxivSource(PreprintSource):
    """Fetch new papers from a server on the bioRxiv API; subclasses supply its data."""

    _server: str
    _site: str

    @property
    def request_delay_seconds(self) -> float:
        # The API publishes no rate limit;
        # this is a self-imposed gap, matching arXiv's request limit
        return 3.0

    def landing_url(self, source_id: str) -> str:
        # source_id is the versionless DOI; this page redirects to the newest version
        return f"{self._site}/content/{source_id}"

    async def fetch_latest(self, categories: List[str]) -> List[PaperEntry]:
        """Fetch the papers posted yesterday (Eastern Time)."""
        return await self.fetch_by_date(_yesterday_et(), categories)

    async def fetch_by_date(
        self,
        target_date,
        categories: List[str],
    ) -> List[PaperEntry]:
        """Fetch the first versions posted on *target_date* in *categories*.

        The API filters by one category per request. The day's first page
        shows how many pages the whole day takes: if requesting each category
        takes fewer requests, they are fetched one by one, otherwise the rest
        of the day is paged through. Records are filtered here either way.
        Any HTTP or API error raises instead of returning a partial list.
        """
        day = target_date.strftime("%Y-%m-%d")
        wanted = set(categories)

        logger.info(f"\nFetching {self.label} papers posted on {day}")
        logger.info(f"  Categories: {categories}")

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            records, total = await _fetch_page(client, self._server, day, 0)
            pages = math.ceil(total / len(records)) if records else 0
            # With the first page in hand, the rest of the day takes pages - 1
            # requests, and each category at least one.
            if len(wanted) < pages - 1:
                logger.info(f"  Fetching each category instead of all {pages} pages")
                records = []
                for category in sorted(wanted):
                    records += await self._fetch_all(client, day, category=category)
            elif pages > 1:
                records += await self._fetch_all(client, day, cursor=len(records))

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()
        for item in records:
            entry = _entry_from_item(item, self._site, self.name)
            if entry is None or entry.categories[0] not in wanted:
                continue
            if entry.source_id in seen_ids:
                continue
            seen_ids.add(entry.source_id)
            entries.append(entry)

        logger.info(f"  Total: {len(entries)} new papers")
        return entries

    async def _fetch_all(
        self, client: httpx.AsyncClient, day: str, cursor: int = 0, category: Optional[str] = None
    ) -> list:
        """Page through a day's postings from *cursor* on, in *category* if given.

        It runs after the day's first page, so every request waits first.
        """
        records: list = []
        while True:
            await asyncio.sleep(self.request_delay_seconds)
            items, total = await _fetch_page(client, self._server, day, cursor, category=category)
            records += items
            # The cursor is the start point of the next page, so advance by what came back.
            cursor += len(items)
            if not items or cursor >= total:
                return records


def _yesterday_et(now: Optional[datetime] = None) -> date:
    """Yesterday's date in Eastern Time; *now* is for tests."""
    now = now or datetime.now(_EASTERN)
    return (now.astimezone(_EASTERN) - timedelta(days=1)).date()


def _entry_from_item(item: dict, site: str, source: str) -> Optional[PaperEntry]:
    """Convert one API record into a PaperEntry, or None unless it is version 1.

    Only version 1 is a new paper, as arXiv keeps only ``announce_type == 'new'``.
    """
    if str(item.get("version")) != "1":
        return None

    doi = item["doi"]

    # Papers reach the daily run the day after posting, so date them with that day.
    posted = date.fromisoformat(item["date"])
    run_day = datetime.combine(posted + timedelta(days=1), time(), _EASTERN)
    return PaperEntry(
        source_id=doi,
        title=item.get("title", "").strip(),
        abstract=item.get("abstract", "").strip(),
        url=f"{site}/content/{doi}",
        pdf_url=f"{site}/content/{doi}v1.full.pdf",
        authors=[a.strip() for a in item.get("authors", "").split(";") if a.strip()],
        categories=[item["category"]],
        # The record's own "published" is a journal DOI (or "NA"), not a date.
        published=run_day.isoformat(),
        source=source,
        # published is shifted to the run day, so keep the server's own posting date too.
        metadata={"posted": item["date"]},
    )


async def _fetch_page(
    client: httpx.AsyncClient,
    server: str,
    day: str,
    cursor: int,
    category: Optional[str] = None,
) -> Tuple[list, int]:
    """Fetch one page of a day's postings as ``(items, total)``, in *category* if given.

    The API reports errors with HTTP 200 and a ``status`` message, so both
    are checked. "no posts found" is not an error: the day has no postings
    left from *cursor* on.
    """
    url = f"{_API_ROOT}/{server}/{day}/{day}/{cursor}"
    if category:
        # Codes are lowercase words; the API takes them with underscores for spaces.
        url += "?category=" + category.replace(" ", "_")
    resp = await client.get(url)
    resp.raise_for_status()
    data = resp.json()

    status = data["messages"][0].get("status")
    if status == "no posts found":
        return [], 0
    if status != "ok":
        raise RuntimeError(f"{server} API error for {day} at cursor {cursor}: {status}")

    # An unknown category is no error to the API: it returns every category, as "all".
    # Treat it as having no posts, as paging through the whole day would.
    if category and data["messages"][0].get("category") == "all":
        logger.warning(f"  {server} API doesn't know category {category!r}; skipped")
        return [], 0

    # The API sends "total" as a string; convert it before comparing with cursor.
    return data.get("collection", []), int(data["messages"][0]["total"])
