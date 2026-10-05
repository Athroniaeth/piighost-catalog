# piighost catalog

[![CI](https://github.com/Athroniaeth/piighost-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost-hub/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](.python-version)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/vFg9GHQR2s)

**[catalog.piighost.dev](https://catalog.piighost.dev)**

A registry of tested de-identification regexes for [piighost](https://github.com/Athroniaeth/piighost): **147 patterns** and **48 groups** across **28 countries**, each addressed by name and version, each carrying the cases it must catch and the cases it must leave alone.

Writing a regex for a national identifier is easy. Writing one that still behaves when it sits next to twenty others is not. A French SIRET is fourteen digits, which is also a credit card number; a five-digit postcode is French, Italian and American at once; a token inside a URL is claimed by the URL first. The registry exists because those collisions are the actual work, and because everyone rewrites the same twenty patterns badly.

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("piighost/logs:fd79aec6")
found = await detector.detect("mail me at a@b.co from 10.0.0.1")
```

An object is versioned by its content: its identifier is the sha256 of its frozen manifest, and you pin it by commit (`piighost/fr-default:7cc7cb30`) or by a movable tag each namespace sets in its own (`alice/support:prod`). The `piighost` namespace sets none: an official object has `latest` and its commits, and nothing else moves under you.

## What the registry guarantees

Every object in it has passed the same checks, run in CI on every change:

- **Its own examples.** A pattern declares what it must catch and what it must not, with the exact value expected. `piighost/fr-siret` catches `732 829 320 00074` in a sentence and leaves `7328293200007` alone.
- **Its examples once composed.** This is the one that matters. When a group assembles twenty patterns, each contributing pattern's examples are replayed _against the whole group_ and must still come out with the right label. A card pattern that steals a SIRET fails the build, not a user's text.
- **A bound on its backtracking.** Each pattern ships a hostile string — a valid prefix, an ambiguous fragment repeated to 100 000 characters, an ending that forbids the match — and must survive it. A regex that backtracks catastrophically never lands.
- **Its vocabulary.** Tags come from a closed list of 55, so a facet means the same thing on every object.

What it does **not** guarantee: anything about a model detector. The checks replay examples, bound backtracking and verify composition, none of which mean anything for a GLiNER2 step. Two configurations carry one, and their pages say so.

## Using it

### From Python

```python
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("piighost/logs:fd79aec6")
found = await detector.detect(text)
```

A reference pinned to a commit is immutable, so it is cached on disk and fetched once. A tag or `latest` moves, so it is fetched every time.

> [!NOTE]
> `RegexDetector.from_catalog` and the `catalog:` references below need piighost 2.0. From 1.8 on, a 1.x release reads the same references under their former names, `RegexDetector.from_hub` and `hub:`. On an older piighost, fetch `pipeline.toml?part=detector` over HTTP and pass `config["detector"]["patterns"]` to `RegexDetector`.

### From a pipeline file

```toml
[detector]
type = "regex"
catalogs = ["catalog:piighost/logs:fd79aec6"]

# Your own on top: an inline pattern wins on a shared label.
[detector.patterns]
INTERNAL_ID = 'EMP-\d{6}'
```

### Over HTTP

```bash
curl 'https://catalog.piighost.dev/api/v1/refs/piighost/logs/latest/pipeline.toml?part=detector'
```

`part=detector` keeps the detector alone, without the stages a configuration chose on your behalf. Drop it for the whole pipeline, add `?keep_refs=true` to get a file that names its catalog references instead of inlining them, and `?memory=redis` to append a memory section.

## Contributing a pattern

The [contribution page](https://catalog.piighost.dev/contribute) runs the maintainers' own checks on a manifest you write in a form, lets you try it against a real text in your browser, and then hands you a prefilled GitHub link. No account, no token, no write access to this repository from the service: the pull request is yours.

Starting from an existing object is one click, which is usually the right move — a pattern that already passes composition is a better base than a blank field.

## Running it

```bash
just install                                      # uv sync + pnpm install
just dev                                          # the site on http://127.0.0.1:5173
just check                                        # what CI runs: lint, tests, registry
```

```bash
just hub-check                                    # validate the registry alone
just hub-record                                   # record the heads as immutable commits
uv run python -m backend.hub resolve piighost/fr  # what a reference contains
uv run python -m backend.hub render piighost/fr-default --memory redis
```

The manifests are in `registry/`, the engine in `backend/hub/`, the site in `frontend/src/`. The backend is Litestar 2.24 behind Granian, the frontend Svelte 5 with Vite 8 and Tailwind 4; `openapi.json` is versioned at the root and the TypeScript client is derived from it, so the two halves cannot drift.

## Documentation

| Document                                                     | Contents                                                  |
| ------------------------------------------------------------ | --------------------------------------------------------- |
| [Manifest format](docs/hub/en/manifest.md)                   | patterns, groups, configurations, samples, tags           |
| [References, commits, resolution](docs/hub/en/resolution.md) | the grammar, the commits, composition rules, the checks   |
| [HTTP API](docs/hub/en/api.md)                               | the routes, the caching, the playground's limits          |
| [The site](docs/hub/en/site.md)                              | the pages and the choices that show                       |
| [Coverage](docs/hub/en/coverage.md)                          | what the registry is measured against, and what it misses |
| [What piighost owes the catalog](docs/hub/en/library-support.md) | the contract for `catalog:` support in the library    |
| [Measuring usage](docs/hub/en/analytics.md)                  | what is measured, what deliberately is not                |
| [En français](docs/hub/)                                     | les sept documents, en version originale                  |

## Project

- **Community**: [Discord](https://discord.gg/vFg9GHQR2s) to get help, report a bad pattern, or propose a country pack
- **Ecosystem**:
  - **[piighost](https://github.com/Athroniaeth/piighost)**: the de-identification library this registry feeds
  - **[piighost-api](https://github.com/Athroniaeth/piighost-api)**: the inference API server
  - **[piighost-chat](https://github.com/Athroniaeth/piighost-chat)**: an example chat interface with human-in-the-loop
- **License**: [MIT](LICENSE)
