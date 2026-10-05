# Manifest format

The registry is a tree of TOML files. Every publishable object, pattern, group
or configuration, lives in its own directory with a manifest and, if it carries
movable tags, a `tags.toml`. This document describes each file. How they resolve
into commits and pipelines is in [resolution.md](resolution.md).

```
registry/
  vocabulary.toml                 closed tag vocabulary
  patterns/<ns>/<name>/pattern.toml
  groups/<ns>/<name>/group.toml
  configs/<ns>/<name>/config.toml
  samples/<name>/sample.toml      annotated texts, not versioned
  <kind>/<ns>/<name>/tags.toml    tag pointers, optional
  commits/<ns>/<name>/<short>.json  immutable snapshots, written by `hub record`
```

Rules that apply everywhere:

- `schema_version = 1` at the top of every manifest. This is the version of the
  format, never of the object: an object's version is its commit, and it is
  never written into the file.
- A namespace and a name are kebab-case (`^[a-z0-9][a-z0-9-]*$`). The name in
  the manifest must equal the name of its directory.
- An unknown key is an error, not a warning.
- Tags are a flat list, but every tag must exist in `vocabulary.toml`.
- Descriptions are bilingual, `{ en = "...", fr = "..." }`.

## `vocabulary.toml`

One tag per table. `kind` is what the site derives its facets from; the author
of a manifest does not need to know about it.

```toml
[fr]
kind = "region"
label = { en = "France", fr = "France" }

[government-id]
kind = "category"
label = { en = "Government identifier", fr = "Identifiant d'État" }
```

The kinds in use: `region`, `category`, `domain`, `use-case`, `language`. Three
families are never typed, they are derived: official or community comes from the
namespace, regex only or local model or API key comes from what a configuration
holds, withdrawn comes from a commit's status.

## `pattern.toml`

One regex, one label, its examples.

```toml
schema_version = 1

[pattern]
name = "fr-nir"
label = "FR_NIR"
tags = ["fr", "government-id", "health"]
regex = '\b[12][\s.-]?\d{2}[\s.-]?(?:0[1-9]|1[0-2])[\s.-]?(?:2A|2B|\d{2})[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}\b'
resilience = true          # optional, defaults to true

[pattern.description]
en = "French social security number (NIR). Shape only, no checksum."
fr = "Numéro de sécurité sociale français (NIR). Forme seule, sans clé."

[[examples.match]]
text = "NIR : 1 85 05 78 006 084 36."
value = "1 85 05 78 006 084 36"

[[examples.no_match]]
text = "180137505600157"

[redos]                    # optional
prefix = "1 85 01 "
filler = "75 "
suffix = "x"
```

| Key | Rule |
|---|---|
| `label` | `^[A-Z][A-Z0-9_]*$`, the label the detector emits |
| `regex` | Python `re`, compiled with `re.ASCII` and no other flag. An inline flag such as `(?i)` goes in the pattern itself. Prefer a TOML literal string `'...'`, so backslashes stay single |
| `examples.match` | at least one. `value` is the exact substring expected and must appear exactly once in `text` |
| `examples.no_match` | at least one. The pattern must detect nothing in `text` |
| `resilience` | when true, each `value` is also tried wrapped in adjacent punctuation (`{v}.`, `{v},`, `{v}\n`, ` {v} `, `({v})`, `Reach me at {v}.`) and must be detected alone and whole |
| `redos` | an adversarial recipe: a valid prefix, an ambiguous fragment repeated up to 100,000 characters, an ending that forbids the match. With no recipe, eight generic fragments are tried |

Examples are synthetic, with no exception: reserved domains (`example.com`),
documentation ranges (RFC 5737 for IPv4, RFC 3849 for IPv6, 555-01xx for
American numbers), test IBANs and cards, invented identifiers. No real value,
not even a public one.

## `group.toml`

A group holds no regex. It composes references in an order, with an exclusion
per source.

```toml
schema_version = 1

[group]
name = "fr-notariat"
description = { en = "French notarial deeds", fr = "Actes notariés français" }
tags = ["fr", "notarial"]

[[sources]]
ref = "piighost/fr-siret"

[[sources]]
ref = "piighost/fr"
exclude = ["FR_PHONE"]

[[sources]]
ref = "piighost/generic"
only = ["EMAIL", "URL"]
```

| Key | Rule |
|---|---|
| `sources` | at least one entry, in the insertion order you want |
| `sources[].ref` | a pattern or a group, with a tag, a commit or bare (`latest`) |
| `sources[].exclude` | labels of that source to drop; each must exist in the source |
| `sources[].only` | labels of that source to keep, mutually exclusive with `exclude` |

A pattern is a group of one label, so a source can be either. There is no global
exclusion after the merge: everything is said in the block of the source it
concerns.

## `config.toml`

A configuration describes a piighost pipeline without its deployment sections.
Its detectors carry a name, which is what gives inheritance something to hold.

```toml
schema_version = 1

[config]
name = "fr-default"
description = { en = "French default", fr = "Défaut français" }
tags = ["fr", "chat"]
piighost = ">=2.0,<3"

[[extends]]
ref = "piighost/regex-default"
exclude = ["detector:regex-us", "label:CREDIT_CARD", "stage:guard"]

[[detectors]]
name = "regex-fr"
type = "regex"
groups = ["piighost/fr-extended", "piighost/eu"]

[[detectors]]
name = "ner-fr"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON", "ADDRESS"]
threshold = 0.5

[stages.expander]
type = "word_boundary"

[stages.anonymizer.placeholder]
type = "label_counter"
```

| Key | Rule |
|---|---|
| `piighost` | a PEP 440 version specifier, optional but recommended; the check refuses to validate a configuration against a version it excludes |
| `extends[].ref` | a parent configuration |
| `extends[].exclude` | prefixed: `detector:<name>`, `label:<LABEL>`, `stage:<section>`; each target must exist in the parent |
| `detectors[].name` | kebab-case, unique within the configuration and among the inherited detectors |
| `detectors[].type` | a piighost detector type. Other keys are passed through to piighost, which validates them |
| a `regex` `detectors[]` | carries `groups`, a list of references, and nothing else. An inline regex would route around the tested patterns |
| `stages` | one table per piighost section: `linker`, `anonymizer`, `overlap_resolver`, `expander`, `entity_resolver`, `guard`, `override`, `observation_redactor`. Passed through as written |
| `memory`, `token_memo_ttl` | refused: the operator adds these at export or at load time |

## `tags.toml`

An object's movable pointers, set by the owner of the namespace.

```toml
prod = "3fa9c2e1"
preprod = "9c8e7f6a"
```

A tag is kebab-case, is not `latest`, and is not made only of hexadecimal
characters. It points at a commit recorded in `commits/`. The `latest` tag never
appears here: it is computed, and always means the working head.

## `sample.toml`

An annotated text. Samples feed the playground and serve as a measuring corpus.
They are data, not published artefacts: nobody pins a sample, so unlike a
pattern it carries neither commit nor tag, and it lives in a single namespace.

```toml
schema_version = 1

[sample]
name = "email-pro-fr"
title = { en = "Business email (French)", fr = "E-mail professionnel (français)" }
tags = ["fr", "lang-fr", "customer-support"]
text = """
Bonjour, je suis joignable au 06 39 98 12 34.
"""

[[annotations]]
value = "06 39 98 12 34"
label = "FR_PHONE"
```

| Key | Rule |
|---|---|
| `text` | the text, as a multiline string |
| `annotations[].value` | a value a good pipeline has to catch; it must appear in the text |
| `annotations[].label` | the expected label, in UPPER_SNAKE |

Annotation is by value rather than by position: a position breaks the moment
someone fixes a typo in the text, and every occurrence of an annotated value is
expected.

The same rules about synthetic data apply as for patterns. A sample annotated
`PERSON` on an invented name is useful even though no regex pattern will find
it: that is what shows what a configuration without a model lets through.
