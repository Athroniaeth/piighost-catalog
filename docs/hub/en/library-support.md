# What is `piighost`'s to do

The catalog publishes, checks and serves. Consuming a reference from a
deployment is the library's job, and that work lives in its repository, not
here. This document fixes the contract so the two sides can move separately,
and says what piighost 2.0 ships of it.

Nothing requires that support: the **flattened** export inlines every regex, so
a downloaded file runs on `piighost` 1.7 unchanged. `catalog:` support removes
the download step; it does not unlock a use.

## Resolving a reference in `catalogs`

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/generic", "catalog:alice/fr-extended:prod"]
```

Since 2.0, `RegexDetectorConfig.catalogs` accepts catalog references only:
piighost ships no pattern of its own, and the former literals (`generic`, `us`,
`eu`, `fr`) are refused with the reference that replaces them. A reference is
resolved **at construction** (`build()`) and never at validation, so that
`piighost validate` stays offline and fast. The merge does not change:
catalogs first, in order, then the inline patterns, which is already the
insertion order the catalog guarantees.

The `hub:` prefix of the 1.x releases is still read exactly as `catalog:` is.

## From Python

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("piighost/logs:fd79aec6")
```

`RegexDetector.from_catalog` builds a detector from a reference, and
`piighost.catalog.pull` returns a reference's regexes as a mapping. The 1.x
names remain as aliases: `RegexDetector.from_hub` delegates to `from_catalog`,
and `piighost.hub` re-exports `piighost.catalog`.

## Loading a whole configuration

```python
from piighost.config import load_pipeline

pipeline = load_pipeline("catalog:alice/fr-default:prod")
```

`load_config`, `load_pipeline` and `load_thread_pipeline` take a path or a
`catalog:` reference, fetched from
`/api/v1/refs/{ns}/{name}/{selector}/pipeline.toml` in its flattened form. A
catalog configuration never carries a `[memory]` section, so
`load_thread_pipeline` refuses it; the caller supplies their own memory, through
the `PIIGHOST_MEMORY` environment override or the programmatic path.

## Cache and mirror

A commit is immutable, so a reference pinned to a commit is kept on disk, under
`~/.cache/piighost/catalog` (or `$XDG_CACHE_HOME`), and fetched once. A tag or
`latest` moves, so it is fetched every time; the API already announces this in
its headers.

| Variable | Role | Default |
|---|---|---|
| `PIIGHOST_CATALOG_URL` | base URL, for an internal mirror | `https://catalog.piighost.dev` |
| `PIIGHOST_HUB_URL` | former name, read when `PIIGHOST_CATALOG_URL` is unset | unset |

## What is not shipped

The contract planned more, which 2.0 does not have. The library has no CLI
subcommand for the catalog: no `pull`, no `lock`, no `verify`. It knows no
`piighost.lock`, no offline mode, no token for a private mirror and no
configurable cache directory. A configuration is declarative data rather than
code, but resolving one over the network at start-up is still a dependency:
until a lock exists, pinning by commit and an internal mirror are the two ways a
deployment avoids having one at the moment it starts.

## One limit only the library can lift

Two patterns covering the same span are settled by insertion order, since every
regex detection has a confidence of 1. That settles identical spans, not
different but overlapping ones: on `01.99.00.12.34` an IPv4 starting at the same
place but ending earlier beats the French phone, whatever the order. The catalog
worked around that case by tightening its IPv4 pattern, which was correct
anyway, but the general lever, a per-pattern priority in `RegexDetector`, is on
the library's side.
