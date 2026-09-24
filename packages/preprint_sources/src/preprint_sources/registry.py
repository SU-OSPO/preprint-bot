"""Registry of available preprint sources.

Adding a source: implement PreprintSource in a new module, then add it to
``_CLASSES`` below. Enablement is env-driven (PREPRINT_ENABLED_SOURCES) so
every consumer resolves the same set.

The development-only ``demo`` source is the exception: it is added to
``_CLASSES`` only when explicitly named in PREPRINT_ENABLED_SOURCES, so it
stays invisible to normal deployments rather than merely disabled.
"""

from __future__ import annotations

import os
from typing import Dict, List, Type

from .arxiv import ArxivSource
from .base import PreprintSource

_CLASSES: Dict[str, Type[PreprintSource]] = {
    "arxiv": ArxivSource,
}

_DEMO_NAME = "demo"


def _env_names() -> List[str]:
    """Raw source names requested via the environment."""
    raw = os.environ.get("PREPRINT_ENABLED_SOURCES", "arxiv")
    return [n.strip() for n in raw.split(",") if n.strip()]


# Registered on request only, so ``demo`` never reaches all_source_names(),
# Paper.SOURCE_CHOICES, or the category picker unless a developer asks for it
# with PREPRINT_ENABLED_SOURCES=arxiv,demo.
if _DEMO_NAME in _env_names():
    from .demo import DemoSource

    _CLASSES[_DEMO_NAME] = DemoSource


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
    names = [n for n in _env_names() if n in _CLASSES]
    return list(dict.fromkeys(names))


def enabled_sources() -> List[PreprintSource]:
    """Instantiated sources that are currently enabled."""
    return [_CLASSES[n]() for n in enabled_names()]
