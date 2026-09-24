"""Registry glue for the web app.

Views and templates need a little more than the raw :mod:`preprint_sources`
registry: a bridge from synchronous Django views into the sources' async API,
and a JSON-friendly description of what each enabled source can do so the
add-paper UI can render itself instead of hardcoding arXiv.
"""

from __future__ import annotations

import asyncio
from typing import Dict, Iterator, List, Optional

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
    return next((s for s in enabled_sources() if getattr(s, capability)()), None)


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


# ── Categories ─────────────────────────────────────────────────────────


def _walk(nodes: List[dict]) -> Iterator[dict]:
    """Yield every node of a category tree, parents before children."""
    for node in nodes:
        yield node
        yield from _walk(node.get("children") or [])


def category_trees() -> List[dict]:
    """Per-source category trees for the picker, in registry order.

    Each entry is ``{"name", "label", "tree"}``. The picker renders one
    group per entry, so a single-source deployment gets a flat tree.
    """
    return [
        {"name": src.name, "label": src.label, "tree": src.category_tree()}
        for src in enabled_sources()
    ]


def leaf_codes_by_source() -> Dict[str, set]:
    """Selectable leaf codes per enabled source, for form validation."""
    return {src.name: src.leaf_codes() for src in enabled_sources()}


def code_to_label_by_source() -> Dict[str, Dict[str, str]]:
    """Category code to human label, nested per source."""
    return {
        src.name: {node["value"]: node["label"] for node in _walk(src.category_tree())}
        for src in enabled_sources()
    }


def multiple_sources_enabled() -> bool:
    """Whether more than one source is turned on."""
    return len(enabled_names()) > 1


def order_source_names(names) -> List[str]:
    """Source names in registry order, with unregistered ones last.

    Keeps every grouped-by-source list on the site in the same order, and still
    renders a source a profile references after it left the registry.
    """
    wanted = set(names)
    registry = [src.name for src in enabled_sources()]
    known = [n for n in registry if n in wanted]
    return known + sorted(wanted - set(registry))


def category_label(source_name: str, code: str) -> str:
    """Human label for *code* as that source names it, else the bare code."""
    src = enabled_source(source_name)
    return src.label_for(code) if src is not None else code


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
