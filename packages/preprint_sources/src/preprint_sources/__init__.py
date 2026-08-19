"""preprint_sources: fetch, taxonomy, and URLs for preprint servers.

A light, dependency-lean package (httpx / feedparser / pylatexenc) shared by
the pipeline and the web app so neither hardcodes server-specific details.
"""
from .arxiv import ArxivSource
from .base import PaperEntry, PreprintSource
from .registry import (
    all_source_names,
    enabled_names,
    enabled_sources,
    get_source,
)

__version__ = "0.1.0"

__all__ = [
    "PaperEntry",
    "PreprintSource",
    "ArxivSource",
    "all_source_names",
    "get_source",
    "enabled_names",
    "enabled_sources",
]
