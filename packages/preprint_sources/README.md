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

## The `demo` source (development only)

`demo.py` is a stand-in second server for exercising multi-source behaviour
before a real one exists — the category picker's per-source tabs, per-source
validation, grouped paper badges, and the add-paper tabs hiding a capability a
source lacks (`demo` supports neither search nor add-by-id).

It is registered **only** when named in `PREPRINT_ENABLED_SOURCES`, so by
default it is absent from `all_source_names()`, `Paper.SOURCE_CHOICES`, the
admin, and the picker — not merely disabled. `fetch_latest` returns nothing, so
enabling it cannot put fabricated papers in the database.

```bash
# Two-source UI, from django_site/
PREPRINT_ENABLED_SOURCES=arxiv,demo python manage.py runserver
```

Then open a profile's edit page: the picker shows an **arXiv** tab, a **Demo
Server** tab, and the source-add control. Note that `demo` adds a value to
`Paper.source`'s `choices`, so `makemigrations` will report an unapplied model
change while it is on; that is cosmetic (choices carry no SQL) and goes away
when you unset the variable. Do not commit a migration generated in this mode.

## Development

From `packages/preprint_sources/`:

```bash
pip install -e ".[test]"
pytest
```
