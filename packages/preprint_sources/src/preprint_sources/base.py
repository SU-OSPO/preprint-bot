"""Base classes for preprint sources.

Each preprint server (arXiv, bioRxiv, ...) implements PreprintSource so the
pipeline can fetch new papers and the web app can render category pickers and
source-aware links without knowing server-specific details.
"""
from __future__ import annotations

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
    and add-by-id (``normalize_id`` / ``fetch_one``).
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
        self, *, title: str = "", author: str = ""
    ) -> List[PaperEntry]:
        raise NotImplementedError(f"{self.name} does not support search")

    # ── add by id (optional) ───────────────────────────────────────

    def supports_add_by_id(self) -> bool:
        return False

    def normalize_id(self, raw: str) -> Optional[str]:
        """Parse a user-typed id/DOI/URL into a canonical source_id, or None."""
        raise NotImplementedError(f"{self.name} does not support add-by-id")

    async def fetch_one(self, source_id: str) -> Optional[PaperEntry]:
        raise NotImplementedError(f"{self.name} does not support add-by-id")
