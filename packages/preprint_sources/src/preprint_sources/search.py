"""Base class for search providers.

Search is kept apart from PreprintSource because one search service can cover
several servers: Europe PMC indexes both bioRxiv and medRxiv, and OSF's index
covers every server OSF hosts. Each result is a PaperEntry whose ``source``
names the server it belongs to, so consumers link and add it through that
server's PreprintSource.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .base import PaperEntry


class SearchProvider(ABC):
    """Interface for a title/author search over one or more preprint servers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. ``'arxiv'``."""
        ...

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-facing name for the UI, e.g. ``'arXiv'``."""
        ...

    @property
    @abstractmethod
    def sources(self) -> List[str]:
        """Names of the sources whose papers this provider can return."""
        ...

    @property
    def request_delay_seconds(self) -> float:
        """Minimum gap between successive searches against this service."""
        return 0.0

    @abstractmethod
    async def search(
        self, *, title: str = "", author: str = "", max_results: int = 100
    ) -> List[PaperEntry]:
        """Find papers by title and/or author, newest first."""
        ...
