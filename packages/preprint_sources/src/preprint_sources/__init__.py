"""preprint_sources: fetch, search, taxonomy, and URLs for preprint servers.

A light, dependency-lean package (httpx / feedparser / pylatexenc) shared by
the pipeline and the web app so neither hardcodes server-specific details.
"""

from .arxiv import ArxivSearchProvider, ArxivSource
from .base import PaperEntry, PreprintSource
from .biorxiv import BiorxivSource
from .europepmc import EuropePmcSearchProvider
from .medrxiv import MedrxivSource
from .registry import (
    all_search_provider_names,
    all_source_names,
    enabled_names,
    enabled_search_providers,
    enabled_sources,
    get_search_provider,
    get_source,
)
from .search import SearchProvider

__version__ = "0.1.0"

__all__ = [
    "PaperEntry",
    "PreprintSource",
    "SearchProvider",
    "ArxivSource",
    "ArxivSearchProvider",
    "EuropePmcSearchProvider",
    "BiorxivSource",
    "MedrxivSource",
    "all_source_names",
    "get_source",
    "enabled_names",
    "enabled_sources",
    "all_search_provider_names",
    "get_search_provider",
    "enabled_search_providers",
]
