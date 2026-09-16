"""Base classes for preprint sources.

Each preprint server (arXiv, bioRxiv, ...) implements PreprintSource so the
pipeline can fetch new papers and the web app can render category pickers and
source-aware links without knowing server-specific details.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PaperEntry:
    """Normalized paper data from any preprint source.

    Every source converts its native format (RSS, API JSON, ...) into this
    common shape before the pipeline touches it.
    """
    source_id: str          # server-specific id, e.g. "2401.12345" or a DOI
    title: str
    abstract: str
    url: str                # landing page (abstract URL)
    pdf_url: str            # direct link to the PDF
    authors: List[str]
    categories: List[str]   # in this source's taxonomy
    published: str          # ISO datetime string (original submission)
    source: str             # "arxiv", "biorxiv", ...
    metadata: dict = field(default_factory=dict)  # extra server-specific data


class PreprintSource(ABC):
    """Interface for a preprint server.

    Required: ``name``, ``label``, ``fetch_latest``, ``landing_url``,
    ``category_tree``, ``leaf_codes``. The rest are optional capabilities a
    source declares support for and implements: ``fetch_by_date``, ``search``,
    and add-by-id (``normalize_id`` / ``fetch_one`` / ``fetch_many``).
    """

    # ── identity ───────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier stored on each paper, e.g. ``'arxiv'``."""
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-facing name for UI badges, e.g. ``'arXiv'``."""
        ...

    @property
    def request_delay_seconds(self) -> float:
        """Minimum gap between successive requests to this server.

        Servers that publish a rate limit (e.g., arXiv asks for one request every
        three seconds) override this; consumers that loop over ids pace
        themselves with this value instead of hardcoding a per-server number.
        """
        return 0.0

    # ── fetching ───────────────────────────────────────────────────

    @abstractmethod
    async def fetch_latest(self, categories: List[str]) -> List[PaperEntry]:
        """Fetch papers from the most recent announcement."""
        ...

    async def fetch_by_date(
        self, target_date, categories: List[str]
    ) -> List[PaperEntry]:
        """Fetch papers for a specific historical date (optional)."""
        raise NotImplementedError(
            f"{self.name} does not support fetching by date"
        )

    # ── identity URLs ──────────────────────────────────────────────

    @abstractmethod
    def landing_url(self, source_id: str) -> str:
        """Abstract/landing page URL for a paper id."""
        ...

    # ── taxonomy ───────────────────────────────────────────────────

    @abstractmethod
    def category_tree(self) -> List[Dict]:
        """Nested tree for the UI picker: ``[{label, value, children?}]``."""
        ...

    @abstractmethod
    def leaf_codes(self) -> set:
        """Valid leaf category codes, for form validation."""
        ...

    def label_for(self, code: str) -> str:
        """Human label for a category code (defaults to the code itself)."""
        return code

    # ── search (optional) ──────────────────────────────────────────

    def supports_search(self) -> bool:
        return False

    async def search(
        self, *, title: str = "", author: str = "", max_results: int = 100
    ) -> List[PaperEntry]:
        """Find papers by title and/or author, newest first."""
        raise NotImplementedError(f"{self.name} does not support search")

    # ── add by id (optional) ───────────────────────────────────────

    def supports_add_by_id(self) -> bool:
        return False

    @property
    def id_hint(self) -> str:
        """Example ids for the add-by-id input's placeholder (optional)."""
        return ""

    def normalize_id(self, raw: str) -> Optional[str]:
        """Parse a user-typed id/DOI/URL into a canonical source_id, or None."""
        raise NotImplementedError(f"{self.name} does not support add-by-id")

    async def fetch_one(self, source_id: str) -> Optional[PaperEntry]:
        """Metadata for a single id, or ``None`` if the server has no record."""
        raise NotImplementedError(f"{self.name} does not support add-by-id")

    async def fetch_many(
        self, source_ids: List[str]
    ) -> Dict[str, PaperEntry]:
        """Metadata for several ids at once, keyed by canonical source_id.

        Defaults to sequential ``fetch_one`` calls paced by
        ``request_delay_seconds``; sources with a batch endpoint should
        override this to avoid one round trip per id.  Ids the server does
        not know about are simply absent from the result.
        """
        entries: Dict[str, PaperEntry] = {}
        for i, source_id in enumerate(source_ids):
            if i and self.request_delay_seconds:
                await asyncio.sleep(self.request_delay_seconds)
            entry = await self.fetch_one(source_id)
            if entry is not None:
                entries[entry.source_id] = entry
        return entries
