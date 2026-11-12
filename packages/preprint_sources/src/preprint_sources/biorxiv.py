"""
bioRxiv preprint source.

bioRxiv posts new papers every day, so "latest" means the previous day's
postings. Papers carry only a posting date, so the day is counted in
Eastern Time, where bioRxiv is based, rather than in the server's
timezone. That day has always ended, wherever the server runs.
"""

from __future__ import annotations

from .rxiv import RxivSource
from .taxonomies.biorxiv import (
    BIORXIV_CATEGORY_TREE,
    BIORXIV_LEAF_CODES,
    label_for as _biorxiv_label_for,
)


class BiorxivSource(RxivSource):
    """Fetch new papers from bioRxiv via its public API."""

    _server = "biorxiv"
    _site = "https://www.biorxiv.org"

    @property
    def name(self) -> str:
        return "biorxiv"

    @property
    def label(self) -> str:
        return "bioRxiv"

    def category_tree(self) -> list:
        return BIORXIV_CATEGORY_TREE

    def leaf_codes(self) -> set:
        return BIORXIV_LEAF_CODES

    def label_for(self, code: str) -> str:
        return _biorxiv_label_for(code)
