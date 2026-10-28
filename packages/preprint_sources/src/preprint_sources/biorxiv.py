"""
bioRxiv preprint source.

bioRxiv posts new papers every day, so "latest" means the previous day's
postings, in Eastern Time. The clock is explicit so the result matches
arXiv's and doesn't depend on the server's or CI's timezone.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from .base import PaperEntry, PreprintSource
from .settings import USER_AGENT
from .taxonomies.biorxiv import (
    BIORXIV_CATEGORY_TREE,
    BIORXIV_LEAF_CODES,
    label_for as _biorxiv_label_for,
)

_API_BASE = "https://api.biorxiv.org/details/biorxiv"
_CONTENT_BASE = "https://www.biorxiv.org/content"
_EASTERN = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


class BiorxivSource(PreprintSource):
    """Fetch new papers from bioRxiv via its public API."""

    @property
    def name(self) -> str:
        return "biorxiv"

    @property
    def label(self) -> str:
        return "bioRxiv"

    @property
    def request_delay_seconds(self) -> float:
        # bioRxiv publishes no rate limit;
        # this is a self-imposed gap, matching arXiv's request limit
        return 3.0

    def landing_url(self, source_id: str) -> str:
        # source_id is the versionless DOI; this page redirects to the newest version
        return f"{_CONTENT_BASE}/{source_id}"

    def category_tree(self) -> list:
        return BIORXIV_CATEGORY_TREE

    def leaf_codes(self) -> set:
        return BIORXIV_LEAF_CODES

    def label_for(self, code: str) -> str:
        return _biorxiv_label_for(code)

    async def fetch_latest(self, categories: List[str]) -> List[PaperEntry]:
        """Fetch the papers posted yesterday (Eastern Time)."""
        return await self.fetch_by_date(_yesterday_et(), categories)

    async def fetch_by_date(
        self,
        target_date,
        categories: List[str],
    ) -> List[PaperEntry]:
        """Fetch the first versions posted on *target_date* in *categories*.

        The category filter takes one category per request, so the whole day
        is fetched once and filtered here. Any HTTP or API error raises instead
        of returning a partial list.
        """
        day = target_date.strftime("%Y-%m-%d")
        wanted = set(categories)

        logger.info(f"\nFetching bioRxiv papers posted on {day}")
        logger.info(f"  Categories: {categories}")

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()
        cursor = 0

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            while True:
                items, total = await _fetch_page(client, day, cursor)
                for item in items:
                    entry = _entry_from_item(item)
                    if entry is None or entry.categories[0] not in wanted:
                        continue
                    if entry.source_id in seen_ids:
                        continue
                    seen_ids.add(entry.source_id)
                    entries.append(entry)

                # The cursor is the start point of the next page, so advance by what came back.
                cursor += len(items)
                if not items or cursor >= total:
                    break
                await asyncio.sleep(self.request_delay_seconds)

        logger.info(f"  Total: {len(entries)} new papers")
        return entries


# ── Helpers ────────────────────────────────────────────────────────


def _yesterday_et(now: Optional[datetime] = None) -> date:
    """Yesterday's date in Eastern Time; *now* is for tests."""
    now = now or datetime.now(_EASTERN)
    return (now.astimezone(_EASTERN) - timedelta(days=1)).date()


def _entry_from_item(item: dict) -> Optional[PaperEntry]:
    """Convert one API record into a PaperEntry, or None for a revision.

    Only version 1 is a new paper, as arXiv keeps only ``announce_type == 'new'``.
    """
    if str(item.get("version")) != "1":
        return None

    doi = item["doi"]
    return PaperEntry(
        source_id=doi,
        title=item.get("title", "").strip(),
        abstract=item.get("abstract", "").strip(),
        url=f"{_CONTENT_BASE}/{doi}",
        pdf_url=f"{_CONTENT_BASE}/{doi}v1.full.pdf",
        authors=[a.strip() for a in item.get("authors", "").split(";") if a.strip()],
        categories=[item["category"]],
        # The record's own "published" is a journal DOI (or "NA"), not a date.
        published=item["date"],
        source="biorxiv",
    )


async def _fetch_page(client: httpx.AsyncClient, day: str, cursor: int) -> Tuple[list, int]:
    """Fetch one page of a day's postings as ``(items, total)``.

    The API reports errors with HTTP 200 and a ``status`` message, so both
    are checked. "no posts found" is not an error: the day has no postings
    left from *cursor* on.
    """
    resp = await client.get(f"{_API_BASE}/{day}/{day}/{cursor}")
    resp.raise_for_status()
    data = resp.json()

    status = data["messages"][0].get("status")
    if status == "no posts found":
        return [], 0
    if status != "ok":
        raise RuntimeError(f"bioRxiv API error for {day} at cursor {cursor}: {status}")

    # The API sends "total" as a string; convert it before comparing with cursor.
    return data.get("collection", []), int(data["messages"][0]["total"])
