"""
Europe PMC search provider.

Europe PMC indexes preprints from many servers, bioRxiv and medRxiv among
them, and names each record's server, so one search covers both.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Dict, List, Optional

import httpx

from .base import PaperEntry
from .search import SearchProvider
from .settings import USER_AGENT

_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# The API rejects larger pages.
_MAX_PAGE_SIZE = 1000

# Europe PMC's name for each server, keyed by our source name.
_PUBLISHERS: Dict[str, str] = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}
_SOURCE_BY_PUBLISHER = {publisher: name for name, publisher in _PUBLISHERS.items()}

logger = logging.getLogger(__name__)


class EuropePmcSearchProvider(SearchProvider):
    """Title/author search over bioRxiv and medRxiv preprints via Europe PMC."""

    @property
    def name(self) -> str:
        return "europepmc"

    @property
    def label(self) -> str:
        return "Europe PMC"

    @property
    def sources(self) -> List[str]:
        return list(_PUBLISHERS)

    @property
    def request_delay_seconds(self) -> float:
        # No published rate limit; a self-imposed gap, as for the bioRxiv API
        return 3.0

    async def search(
        self,
        *,
        title: str = "",
        author: str = "",
        max_results: int = 100,
        sources: Optional[List[str]] = None,
    ) -> List[PaperEntry]:
        """Phrase-match the title and/or author fields, newest first.

        Both terms are combined with AND when supplied.  Raises
        ``ValueError`` if neither is given, since Europe PMC would otherwise
        return every preprint from these servers.
        """
        parts = []
        if title.strip():
            parts.append(_phrase_term("TITLE", title))
        if author.strip():
            # Commas and periods stop names from matching ("Regev, A" finds nothing).
            parts.append(_phrase_term("AUTH", re.sub(r"[.,;]", " ", author)))
        if not parts:
            raise ValueError("search requires a title or an author")

        wanted = [s for s in self.sources if sources is None or s in sources]
        if not wanted:
            return []
        servers = " OR ".join(f'PUBLISHER:"{_PUBLISHERS[s]}"' for s in wanted)
        query = f"SRC:PPR AND ({servers}) AND " + " AND ".join(parts)
        logger.info(f"\nSearching Europe PMC: {query} (max {max_results})")

        entries: List[PaperEntry] = []
        seen: set[str] = set()
        cursor = "*"
        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            while len(entries) < max_results:
                if cursor != "*":
                    await asyncio.sleep(self.request_delay_seconds)
                items, next_cursor = await _fetch_page(
                    client, query, cursor, min(_MAX_PAGE_SIZE, max_results)
                )
                for item in items:
                    entry = _entry_from_result(item)
                    if entry is None or entry.source_id in seen:
                        continue
                    seen.add(entry.source_id)
                    entries.append(entry)
                # The last page repeats its own cursor as the next one.
                if not items or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
        return entries[:max_results]


async def _fetch_page(
    client: httpx.AsyncClient, query: str, cursor: str, page_size: int
) -> tuple[list, Optional[str]]:
    """Fetch one page of results as ``(items, next_cursor)``.

    The API reports some errors (e.g. a bad page size) with HTTP 200 and an
    ``errMsg``, so both are checked.
    """
    resp = await client.get(
        _SEARCH_URL,
        params={
            "query": query,
            "format": "json",
            "resultType": "lite",
            "sort": "P_PDATE_D desc",
            "pageSize": page_size,
            "cursorMark": cursor,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errMsg"):
        raise RuntimeError(f"Europe PMC search error: {data['errMsg']}")
    return data.get("resultList", {}).get("result", []), data.get("nextCursorMark")


def _phrase_term(field: str, value: str) -> str:
    """Build a phrase term, e.g. ``TITLE:"deep learning"``.

    Double quotes and backslashes are dropped so user input cannot break
    out of the phrase.
    """
    phrase = " ".join(re.sub(r'["\\]', "", value).split())
    return f'{field}:"{phrase}"'


def _plain_text(markup: str) -> str:
    """Titles can carry inline HTML (e.g. ``3 <sup>rd</sup> wave``); drop tags, decode entities."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", markup)).split())


def _entry_from_result(item: dict) -> Optional[PaperEntry]:
    """Convert one search result into a PaperEntry, or None if it is not a covered preprint."""
    publisher = (item.get("bookOrReportDetails") or {}).get("publisher")
    source = _SOURCE_BY_PUBLISHER.get(publisher)
    doi = item.get("doi")
    if source is None or not doi:
        return None
    return PaperEntry(
        source_id=doi,
        title=_plain_text(item.get("title", "")),
        abstract="",  # search results carry no abstract
        url=f"https://doi.org/{doi}",
        # Left empty: adding a result fetches its PDF link from the server by DOI.
        pdf_url="",
        # "Swarna NP, Pachter L." -> ["Swarna NP", "Pachter L"]
        authors=[
            a.strip() for a in item.get("authorString", "").rstrip(".").split(",") if a.strip()
        ],
        categories=[],
        published=item.get("firstPublicationDate", ""),
        source=source,
        metadata={"europepmc_id": item.get("id")},
    )
