"""Registry glue for the web app.

Views and templates need a little more than the raw :mod:`preprint_sources`
registry: a bridge from synchronous Django views into the sources' async API,
and a JSON-friendly description of what each enabled source can do so the
add-paper UI can render itself instead of hardcoding arXiv.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from preprint_sources import (
    PreprintSource,
    enabled_names,
    enabled_sources,
    get_source,
)


def run_sync(coro):
    """Run a source coroutine from a synchronous view.

    Sync views have no running event loop of their own — under WSGI, or in
    the threadpool ASGI hands sync views to — so a fresh loop per call is
    both safe and the simplest thing that works.
    """
    return asyncio.run(coro)


def enabled_source(name: str) -> Optional[PreprintSource]:
    """Look up an *enabled* source by name, or ``None``.

    Unknown and disabled names both return ``None`` so a hand-crafted
    request cannot reach a source the deployment has turned off.
    """
    if not name or name not in enabled_names():
        return None
    return get_source(name)


def describe_sources() -> List[dict]:
    """Enabled sources, described for the add-paper templates and JS."""
    return [
        {
            "name": src.name,
            "label": src.label,
            "supports_search": src.supports_search(),
            "supports_add_by_id": src.supports_add_by_id(),
            "id_hint": src.id_hint,
            # Client-side pacing for the per-id add loop.
            "delay_ms": int(src.request_delay_seconds * 1000),
        }
        for src in enabled_sources()
    ]


def resolve_source(name: str, capability: str) -> Optional[PreprintSource]:
    """The source a request should act on, or ``None``.

    A named source is honoured only if it is enabled and actually supports
    *capability* (``"supports_search"`` / ``"supports_add_by_id"``).  With no
    name — the common case while a deployment runs a single source — the
    first enabled source with that capability is used.
    """
    if name:
        src = enabled_source(name)
        if src is None or not getattr(src, capability)():
            return None
        return src
    return next(
        (s for s in enabled_sources() if getattr(s, capability)()), None
    )


def paper_source_context() -> dict:
    """Template context for the add-paper tabs.

    Each list is empty when no enabled source offers the capability, which
    is how the templates decide whether to render that tab at all.
    """
    sources = describe_sources()
    return {
        "paper_sources": sources,
        "add_sources": [s for s in sources if s["supports_add_by_id"]],
        "search_sources": [s for s in sources if s["supports_search"]],
    }


def source_label(name: str) -> str:
    """Human-facing label for a stored ``Paper.source`` value.

    Falls back to the raw value for sources that have since been removed
    from the registry, so old rows still render something meaningful.
    """
    if name == "user":
        return "User upload"
    try:
        return get_source(name).label
    except KeyError:
        return name or "Unknown"
