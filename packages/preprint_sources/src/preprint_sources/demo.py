"""A stand-in second preprint source, for development only.

Multi-source behaviour — the category picker's tabs, per-source validation,
grouped badges, the capability gating on the add-paper tabs — cannot be
exercised while arXiv is the only registered server. This source exists to
fill that gap until a real second one lands.

It is registered only when ``demo`` is listed in ``PREPRINT_ENABLED_SOURCES``
(see :mod:`preprint_sources.registry`), so a normal deployment never sees it:
not in the picker, not in ``Paper.SOURCE_CHOICES``, not in the admin.

``fetch_latest`` deliberately returns nothing, so enabling it cannot put
fabricated papers into the database even if the pipeline runs.
"""

from __future__ import annotations

import logging
from typing import List

from .base import PaperEntry, PreprintSource

logger = logging.getLogger(__name__)

# Shallower and differently shaped than the arXiv tree, so the two are easy to
# tell apart on screen. ``cs.AI`` repeats an arXiv code on purpose: category
# codes are only unique within a server, and that collision is what the
# per-source validation and the recommendation dedup key need to survive.
DEMO_CATEGORY_TREE: List[dict] = [
    {
        "label": "Life Sciences",
        "value": "life",
        "children": [
            {"label": "Neuroscience (neuro)", "value": "neuro"},
            {"label": "Genomics (genomics)", "value": "genomics"},
            {"label": "Ecology (ecology)", "value": "ecology"},
        ],
    },
    {
        "label": "Methods",
        "value": "methods",
        "children": [
            {"label": "Bioinformatics (bioinfo)", "value": "bioinfo"},
            {"label": "Machine Learning (cs.AI)", "value": "cs.AI"},
        ],
    },
]

_DEMO_LABELS = {
    node["value"]: node["label"]
    for group in DEMO_CATEGORY_TREE
    for node in [group, *group.get("children", [])]
}

DEMO_LEAF_CODES = {
    child["value"] for group in DEMO_CATEGORY_TREE for child in group.get("children", [])
}


class DemoSource(PreprintSource):
    """A fake server with a small taxonomy and no fetching.

    Search and add-by-id are left unsupported (the defaults), which also makes
    this the only way to see the add-paper tabs hide a capability a source
    does not have.
    """

    @property
    def name(self) -> str:
        return "demo"

    @property
    def label(self) -> str:
        return "Demo Server"

    def landing_url(self, source_id: str) -> str:
        # example.invalid is reserved by RFC 2606 and never resolves, so a
        # stray link from demo data cannot reach anything real.
        return f"https://example.invalid/demo/{source_id}"

    def category_tree(self) -> list:
        return DEMO_CATEGORY_TREE

    def leaf_codes(self) -> set:
        return DEMO_LEAF_CODES

    def label_for(self, code: str) -> str:
        return _DEMO_LABELS.get(code, code)

    async def fetch_latest(self, categories: List[str]) -> List[PaperEntry]:
        """Return nothing — this source must never invent papers."""
        logger.info(
            "Demo source is enabled; it fetches nothing " "(categories requested: %s)", categories
        )
        return []
