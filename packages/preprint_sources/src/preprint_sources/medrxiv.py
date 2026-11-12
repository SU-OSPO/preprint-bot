"""
medRxiv preprint source.

Like bioRxiv, medRxiv posts new papers every day and serves them through the
same API, so "latest" means the previous day's postings, counted in Eastern
Time rather than in the timezone of the machine running the pipeline.
"""

from __future__ import annotations

from .rxiv import RxivSource
from .taxonomies.medrxiv import (
    MEDRXIV_CATEGORY_TREE,
    MEDRXIV_LEAF_CODES,
    label_for as _medrxiv_label_for,
)


class MedrxivSource(RxivSource):
    """Fetch new papers from medRxiv via its public API."""

    _server = "medrxiv"
    _site = "https://www.medrxiv.org"

    @property
    def name(self) -> str:
        return "medrxiv"

    @property
    def label(self) -> str:
        return "medRxiv"

    def category_tree(self) -> list:
        return MEDRXIV_CATEGORY_TREE

    def leaf_codes(self) -> set:
        return MEDRXIV_LEAF_CODES

    def label_for(self, code: str) -> str:
        return _medrxiv_label_for(code)
