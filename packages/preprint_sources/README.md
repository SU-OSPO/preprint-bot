# preprint-sources

Light, shared package of **preprint-server source adapters** for Preprint Bot.

Each supported server implements the `PreprintSource` interface: fetching new
papers, its category taxonomy, and source-aware landing/PDF URLs. The package
is deliberately dependency-lean so that **both** the heavy pipeline package
(`preprint_bot`) and the lean Django web app can depend on it without either
pulling in the other's dependencies.

## Layout

```
src/preprint_sources/
  base.py            # PaperEntry, PreprintSource (the interface)
  arxiv.py           # ArxivSource
  taxonomies/        # per-source category trees (e.g. arxiv.py)
  registry.py        # name -> class, enabled_sources()
  settings.py        # USER_AGENT (env-overridable)
```

## Usage

```python
from preprint_sources import get_source, enabled_sources, all_source_names

src = get_source("arxiv")
src.name            # "arxiv"
src.label           # "arXiv"
src.landing_url("2401.12345")   # https://arxiv.org/abs/2401.12345
src.category_tree()             # nested tree for the picker UI
papers = await src.fetch_latest(["cs.AI", "cs.LG"])

# Which sources are on:
#   PREPRINT_ENABLED_SOURCES="arxiv,biorxiv"
for source in enabled_sources():
    ...
```

## Adding a source

1. Implement `PreprintSource` in a new module (e.g., `biorxiv.py`).
2. Register it in `registry.py` `_CLASSES`.
3. Add its name to `PREPRINT_ENABLED_SOURCES`.

## Development

From `packages/preprint_sources/`:

```bash
pip install -e ".[test]"
pytest
```
