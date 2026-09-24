"""
arXiv preprint source.

Primary method: RSS feed (contains exactly the latest announcement).
Fallback: arXiv search API with submission-window calculation (for
backfilling historical dates).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import feedparser
import httpx
from pylatexenc.latex2text import LatexNodes2Text

from .base import PaperEntry, PreprintSource
from .settings import USER_AGENT
from .taxonomies.arxiv import (
    ARXIV_CATEGORY_TREE,
    ARXIV_LEAF_CODES,
    label_for as _arxiv_label_for,
)

_RSS_BASE = "https://rss.arxiv.org/rss"
_API_BASE = "https://export.arxiv.org/api/query"

# Reused across calls; converts LaTeX text markup (e.g. ``\'e``) to Unicode.
_LATEX2TEXT = LatexNodes2Text()

# Canonical arXiv id: modern ``2401.12345`` or legacy ``hep-th/9901001``.
ARXIV_ID_RE = re.compile(r"^(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z-]+)?/\d{7})$", re.IGNORECASE)

logger = logging.getLogger(__name__)


class ArxivSource(PreprintSource):
    """Fetch new papers from arXiv via RSS or the search API."""

    @property
    def name(self) -> str:
        return "arxiv"

    @property
    def label(self) -> str:
        return "arXiv"

    @property
    def request_delay_seconds(self) -> float:
        # arXiv asks for no more than one request every three seconds.
        return 3.0

    def landing_url(self, source_id: str) -> str:
        return f"https://arxiv.org/abs/{source_id}"

    def category_tree(self) -> list:
        return ARXIV_CATEGORY_TREE

    def leaf_codes(self) -> set:
        return ARXIV_LEAF_CODES

    def label_for(self, code: str) -> str:
        return _arxiv_label_for(code)

    # ── RSS (primary) ──────────────────────────────────────────────

    async def fetch_latest(self, categories: List[str]) -> List[PaperEntry]:
        """Fetch the current announcement via the arXiv RSS feed.

        The RSS feed is updated daily at midnight EST and contains
        exactly the papers from the most recent announcement.  We
        filter for ``announce_type == 'new'`` to skip replacements
        and cross-listings.
        """
        # Combine categories with '+' to fetch a single merged feed
        cat_str = "+".join(categories)
        url = f"{_RSS_BASE}/{cat_str}"

        logger.info("\nFetching latest arXiv papers via RSS")
        logger.info(f"  Feed: {url}")
        logger.info(f"  Categories: {categories}")

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
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
                        getattr(item, "description", "") or getattr(item, "summary", "")
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

        logger.info(f"  Found {len(entries)} new papers")
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
            logger.info(
                f"\nNo arXiv announcement on "
                f"{target_date.strftime('%A %Y-%m-%d')} — skipping fetch."
            )
            return []

        start_dt, end_dt = window
        start = start_dt.strftime("%Y%m%d%H%M")
        end = end_dt.strftime("%Y%m%d%H%M")

        logger.info(
            f"\nFetching arXiv papers via API for " f"{target_date.strftime('%A %Y-%m-%d')}"
        )
        logger.info(f"  Submission window: {start_dt} → {end_dt} (UTC)")
        logger.info(f"  Categories: {categories}")

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            # Combine all categories into a single OR query to avoid
            # per-category rate limiting (26 categories = 26 requests)
            cat_query = "+OR+".join(f"cat:{cat}" for cat in categories)
            query = f"({cat_query})+AND+submittedDate:[{start}+TO+{end}]"

            papers = await _api_fetch_all(client, query)
            for item in papers:
                entry = _entry_from_api_item(item)
                if entry is None or entry.source_id in seen_ids:
                    continue
                seen_ids.add(entry.source_id)
                entries.append(entry)

        logger.info(f"  Total: {len(entries)} new papers")
        return entries

    # ── Search (title / author) ────────────────────────────────────

    def supports_search(self) -> bool:
        return True

    async def search(
        self, *, title: str = "", author: str = "", max_results: int = 100
    ) -> List[PaperEntry]:
        """Phrase-match the title and/or author fields, newest first.

        Both terms are combined with AND when supplied.  Raises
        ``ValueError`` if neither is given, since arXiv would otherwise
        return the entire corpus.
        """
        parts = []
        if title.strip():
            parts.append(_phrase_term("ti", title))
        if author.strip():
            parts.append(_phrase_term("au", author))
        if not parts:
            raise ValueError("search requires a title or an author")

        query = "+AND+".join(parts)
        logger.info(f"\nSearching arXiv: {query} (max {max_results})")

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            items = await _api_fetch_all(client, query, limit=max_results)

        entries: List[PaperEntry] = []
        seen_ids: set[str] = set()
        for item in items:
            entry = _entry_from_api_item(item)
            if entry is None or entry.source_id in seen_ids:
                continue
            seen_ids.add(entry.source_id)
            entries.append(entry)
        return entries

    # ── Add by id ──────────────────────────────────────────────────

    def supports_add_by_id(self) -> bool:
        return True

    @property
    def id_hint(self) -> str:
        return "https://arxiv.org/abs/2601.19018, arXiv:2601.19018, or 2301.12345"

    def normalize_id(self, raw: str) -> Optional[str]:
        """Parse a user-typed arXiv id, URL, or ``arXiv:`` reference.

        Accepts ``2601.19018``, ``arXiv:2601.19018``, abstract and PDF
        URLs (with or without a version suffix, query string, fragment,
        or ``.pdf`` extension), and legacy ``hep-th/9901001`` ids.
        Returns the canonical, version-stripped id, or ``None`` if the
        input is not an arXiv id.
        """
        token = (raw or "").strip()
        if not token:
            return None
        token = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", token, flags=re.IGNORECASE)
        if token.lower().startswith("arxiv:"):
            token = token[len("arxiv:") :]
        # Strip query/fragment suffixes, then .pdf, then trailing version
        token = re.sub(r"[?#].*$", "", token)
        token = re.sub(r"\.pdf$", "", token, flags=re.IGNORECASE)
        token = re.sub(r"v\d+$", "", token)
        return token if ARXIV_ID_RE.match(token) else None

    async def fetch_one(self, source_id: str) -> Optional[PaperEntry]:
        """Fetch metadata for a single arXiv id, or ``None`` if unknown."""
        return (await self.fetch_many([source_id])).get(source_id)

    async def fetch_many(self, source_ids: List[str]) -> Dict[str, PaperEntry]:
        """Fetch metadata for many ids in one id_list query."""
        if not source_ids:
            return {}

        async with httpx.AsyncClient(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
            items = await _api_fetch_by_ids(client, list(source_ids))

        entries: Dict[str, PaperEntry] = {}
        for item in items:
            entry = _entry_from_api_item(item)
            if entry is not None:
                entries[entry.source_id] = entry
        return entries


# ── Helpers ────────────────────────────────────────────────────────


def _extract_arxiv_id(link: str) -> str | None:
    """Pull the arXiv ID from an abstract URL, stripping any version."""
    m = re.search(r"abs/([^\s?#]+)", link or "")
    if not m:
        return None
    raw = m.group(1)
    return re.sub(r"v\d+$", "", raw)  # strip version suffix


def _entry_from_api_item(item) -> PaperEntry | None:
    """Convert one arXiv API result into a PaperEntry.

    Returns ``None`` for entries without a usable id — notably the error
    entry arXiv returns for an unknown id_list member.
    """
    arxiv_id = _extract_arxiv_id(getattr(item, "id", ""))
    if not arxiv_id:
        return None
    return PaperEntry(
        source_id=arxiv_id,
        title=item.title.strip(),
        abstract=getattr(item, "summary", "").strip(),
        url=item.id,
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        authors=[a.name for a in getattr(item, "authors", [])],
        categories=[tag.term for tag in getattr(item, "tags", [])],
        published=getattr(item, "published", ""),
        source="arxiv",
        metadata={"arxiv_url": item.id},
    )


def _phrase_term(field: str, value: str) -> str:
    """Build a percent-encoded phrase term, e.g. ``ti:%22deep%20learning%22``.

    Inner double quotes are dropped so a user's stray quote cannot break
    out of the phrase.
    """
    phrase = '"' + value.strip().replace('"', "") + '"'
    return f"{field}:{quote(phrase, safe='')}"


def _clean_rss_title(raw: str) -> str:
    """Remove the 'arXiv:2401.12345' prefix that the RSS feed prepends."""
    return re.sub(r"^arXiv:\S+\s*", "", raw).strip()


def _clean_html(text: str) -> str:
    """Strip HTML tags from RSS description fields."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _latex_to_unicode(text: str) -> str:
    r"""Convert LaTeX text-mode markup to Unicode (``J\'er\^ome`` → ``Jérôme``).

    arXiv encodes author names in LaTeX. Only strings containing a backslash
    are processed, so already-clean Unicode names (and apostrophes such as
    ``O'Brien``) are left untouched. Falls back to the input on error.
    """
    if "\\" not in text:
        return text
    try:
        return _LATEX2TEXT.latex_to_text(text).strip()
    except Exception:
        logger.info(f"Could not convert assumed LaTeX {text} to unicode")
        return text


def _parse_rss_authors(item) -> List[str]:
    r"""Extract author list from an RSS item.

    arXiv's RSS puts all authors in a single ``<dc:creator>`` element
    as one comma-separated string, LaTeX-encoded (e.g. ``J\'er\^ome``).
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
    # Decode LaTeX markup (accents etc.) to Unicode
    return [_latex_to_unicode(n) for n in names]


def _parse_rss_categories(item) -> List[str]:
    """Extract category list from an RSS item."""
    if hasattr(item, "tags") and item.tags:
        return [tag.term for tag in item.tags if hasattr(tag, "term")]
    return []


async def _api_fetch_all(
    client: httpx.AsyncClient,
    query: str,
    page_size: int = 500,
    limit: int | None = None,
) -> list:
    """Fetch all results for a query, paginating as needed.

    The arXiv API caps ``max_results`` at ~30 000, but practical
    pages should be ≤ 500 to avoid timeouts.  We read
    ``opensearch:totalResults`` from the first page to know how
    many pages to fetch.  Pass ``limit`` to only retrieve the
    newest N results.
    """
    all_entries: list = []
    offset = 0
    total: int | None = None  # learned from first response
    if limit is not None:
        page_size = min(page_size, limit)

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

        if limit is not None and len(all_entries) >= limit:
            del all_entries[limit:]
            break

        # Learn total from first response
        if total is None:
            total = feed_total
            if total is not None and total > page_size:
                logger.info(f"  {total} total results, paginating...")

        # Stop if we got fewer than a full page or we've fetched everything
        if len(feed_entries) < page_size:
            break
        if total is not None and len(all_entries) >= total:
            break

        offset += page_size
        await asyncio.sleep(5)  # polite delay between pages

    logger.info(f"  Fetched {len(all_entries)} papers via API")
    return all_entries


async def _api_fetch_by_ids(
    client: httpx.AsyncClient,
    source_ids: list,
) -> list:
    """Fetch metadata for specific arXiv ids via the API's id_list param."""
    ids = ",".join(source_ids)
    url = f"{_API_BASE}?id_list={quote(ids, safe=',')}&max_results={len(source_ids)}"
    result = await _api_fetch_page(client, url)
    return result[0] if result else []


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
                wait = int(retry_after) if retry_after else backoff * (2**attempt)
                logger.info(
                    f"  429 rate limited, waiting {wait}s " f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            total = int(feed.feed.get("opensearch_totalresults", 0)) or None
            return feed.entries, total
        except Exception as e:
            wait = backoff * (2**attempt)
            logger.info(
                f"  API error (attempt {attempt + 1}/{max_retries}): {type(e).__name__}: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(wait)

    logger.info(f"  API fetch failed after {max_retries} attempts")
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
        hour=14,
        minute=0,
        second=0,
        tzinfo=eastern,
    )
    end_dt = datetime(
        year=end_day.year,
        month=end_day.month,
        day=end_day.day,
        hour=14,
        minute=0,
        second=0,
        tzinfo=eastern,
    )
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc)
