"""Registry of available preprint sources.

Adding a source: implement PreprintSource in a new module, then add it to
``_CLASSES`` below. Enablement is env-driven (PREPRINT_ENABLED_SOURCES) so
every consumer resolves the same set.
"""
from __future__ import annotations

import os
from typing import Dict, List, Type

from .arxiv import ArxivSource
from .base import PreprintSource

_CLASSES: Dict[str, Type[PreprintSource]] = {
    "arxiv": ArxivSource,
}


def all_source_names() -> List[str]:
    """Every registered source name, in registration order."""
    return list(_CLASSES)


def get_source(name: str) -> PreprintSource:
    """Instantiate a source by name. Raises KeyError if unknown."""
    return _CLASSES[name]()


def enabled_names() -> List[str]:
    """Sources turned on via PREPRINT_ENABLED_SOURCES (default: ``arxiv``).

    Unknown names in the env var are ignored.
    """
    raw = os.environ.get("PREPRINT_ENABLED_SOURCES", "arxiv")
    names = [n.strip() for n in raw.split(",") if n.strip() in _CLASSES]
    return list(dict.fromkeys(names))


def enabled_sources() -> List[PreprintSource]:
    """Instantiated sources that are currently enabled."""
    return [_CLASSES[n]() for n in enabled_names()]
