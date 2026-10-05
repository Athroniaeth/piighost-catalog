# References, commits and resolution

This document sets out what a reference names, how an object becomes an
immutable commit, and how a group or a configuration resolves into a piighost
pipeline. The file format is in [manifest.md](manifest.md), the HTTP API in
[api.md](../api.md).

## References

```
catalog:alice/fr-notariat:prod            tag, movable, set by the owner
catalog:piighost/fr-notariat:3fa9c2e1     commit, immutable
catalog:piighost/fr-notariat:latest       computed tag, the latest commit
catalog:piighost/fr-notariat              the same as :latest
```

One separator serves both tags and commits. The rule that tells them apart is
syntactic: exactly eight hexadecimal characters name a commit, everything else
is a tag. In exchange a tag cannot be made only of hexadecimal characters, nor
be called `latest`. The `catalog:` prefix is optional in a manifest, where every
reference names a catalog object, and customary in a piighost file, where it
marks a catalog reference. The former `hub:` prefix is still accepted
everywhere, here as in the library.

## Commits

A commit is a content, not a number. At publication each reference in the
manifest is resolved to a commit, the manifest thus pinned is serialised to
canonical JSON (sorted keys, no whitespace, UTF-8 preserved), and its sha256 is
computed. The first eight characters form the short identifier, scoped to one
object.

Consequences:

- A commit is immutable by construction: change a comma and you get another
  hash. Reformatting or commenting the file creates none, since the canonical
  form ignores comments and key order.
- A group's hash covers its sources transitively: change a pattern and you
  change the commit of every group and every configuration that reaches it.
- History only grows. A faulty commit will be marked deprecated with a message;
  it is not deleted.

Commits are recorded under `commits/<ns>/<name>/<short>.json`, with their full
digest and their date. `hub check` recomputes each digest and fails on a
modified file: that is how a rewrite is caught. History lives in these files
rather than in git, so an ingestion does not need `git log` and a mirror is a
plain copy.

An object's working head is the commit its current manifest would produce.
`hub check` requires it to be recorded; `hub record` records the ones that are
not. In this single-repository registry, publishing is therefore pushing a
manifest and then running `record`, and a bare reference (`latest`) follows the
head on every pass, which CI tests as a whole.

## Tags

A tag is a movable pointer, owned by whoever publishes the namespace. `latest`
is computed and always points at the head; nobody moves it by hand. The others,
`prod`, `preprod`, whatever you like, live in the object's `tags.toml` and move
by a git commit, which leaves a trace. A tag must point at a recorded commit.

The `piighost` namespace sets none, deliberately. An official object therefore
has only `latest` and its commits: what is published is what is served, and a
team wanting a staging step keeps it at home, in its own namespace, where it
alone decides when `prod` moves. The mechanism exists for them, not for us.

An author writes tags in their manifests; publication pins them to commits and
stores both, the reference as written and the commit it resolved to:

```json
{"ref": "alice/fr-base:prod", "commit": "b41d09aa", "exclude": ["FR_PHONE"], "only": []}
```

A group therefore never silently follows its parents' `prod` between two
publications.

## Resolving a group

A group resolves into an ordered dictionary of label to regex, exactly the shape
of a piighost catalogue, plus the provenance of each label. Three rules:

1. **A label coming from two sources is an error.** The author settles it by
   excluding it from one of the two, in that source's block, or with `only`.
   No silent overwrite exists. One exception: the same pattern commit reached by
   two paths, a harmless diamond, which is simply de-duplicated.
2. **`exclude` and `only` must name labels the source provides.** A typo is an
   error, not a silence.
3. **The order of the sources is the insertion order in the detector.** Every
   regex has a confidence of 1, and piighost's resolver sorts by confidence then
   by span with a stable sort: on two identical spans, the first inserted wins.
   The catalog adds no rule of its own, it honours the order.

On the third rule, a real case: a fourteen digit SIRET is also a card number by
shape (thirteen to nineteen digits). With `generic` declared before `fr`,
`73282932000074` comes out as `<<CREDIT_CARD:1>>`. The composition check reports
it and the author reorders. A different but overlapping span is always settled
by position rather than by order: a whole IBAN beats the sixteen digits inside
it.

## Composing several countries

A country group is meant to be used on its own, or with groups of another
nature. Stacking them as they are does not work, and the reason is about shape
rather than implementation: national identifiers look alike.

A postal code is five digits in France, Germany, Spain, Italy and the United
States. A nine digit number is an American bank routing number, a Dutch BSN and
a Canadian SIN. Ten bare digits are an NHS number, an American NPI and an
Australian Medicare number. On an identical span the first source declared wins,
so putting two countries in one detector means labelling the second one's values
with the first one's labels.

Three ways out, in order of preference:

1. **One detector per country.** A configuration can carry several, and the
   resolver arbitrates between them as it does between two patterns. This is
   what `regex-default` does with `fr`, `eu`, `us` and `generic`. It does not
   remove the collision, it makes it visible and ordered.
2. **Exclude the ambiguous shape** in the source's block, with `exclude`. A
   multi-country group that keeps one postal code and drops the others is
   honest: it says which country it really serves.
3. **Do not mix.** A configuration named after a country is more useful than one
   claiming to cover the world and getting the label wrong half the time.

This rule was tested rather than assumed. An `eu-countries` group composing
France, Germany, Spain, Italy, the Netherlands and Poland was written, then
refused by the check with nine collisions: the German postal code claims the
Spanish and Italian ones, the Spanish phone claims the Dutch BSN and the Polish
phone, the Italian VAT number claims the PESEL. That group does not exist, and
cannot.

Concept groups do work when their members have distinct shapes, and the check
says which. `payment`, `contact` and `identity-documents` pass as they are.
Three others needed an arbitration, each recorded in the group's description:
`business` drops the Portuguese NIF, nine bare digits that claim the head of a
SIRET; `health` drops the American provider number, ten bare digits
indistinguishable from an NHS number; `logs` drops the URL, which swallows a
token written inside it.

## Who wins a span, exactly

The resolver sorts by `(-confidence, span)` and keeps greedily. A regex's
confidence is always 1, so the span alone decides, and a span is a `(start,
end)` pair sorted ascending. Two consequences, and both surprise:

- **The span that starts earliest wins.** That is the usual intuition.
- **On an equal start, the *shorter* one wins**, not the longer. A pattern that
  recognises the *head* of a longer run therefore shreds it instead of yielding.

It is that second rule that breaks the most patterns, and always the same way:
an eight digit Danish phone sits on the head of a sixteen digit card number, a
twelve digit grouped Aadhaar does too, a Japanese postal code on the head of a
Japanese phone. The remedy is not the source order, which only plays on an
identical span, but the pattern itself: a trailing negative lookahead refusing a
separator followed by another digit.

```
(?<!\w)\d{3}-\d{4}(?!\w)(?![\s.-]?\d)
```

A Japanese postal code written this way no longer claims `090-1234` inside
`090-1234-5678`. Seven patterns in the registry carry this lookahead, every one
added after the composition check caught them out.

When the two spans are *identical*, however, only the source order settles it,
and the rule is to declare the more specific one first. Four groups do so, each
with its reason written into its description: `us` puts the individual taxpayer
number before the social security number, which never opens on a 9; `business`
puts the British VAT number before the European one, the United Kingdom having
left that system; `health` puts the Danish CPR before the NHS number, its
validated birth date being more specific; `international` puts ORCID before the
card number, no card opening on 0000.

What composes without risk, on the other hand, are the groups that do not rest
on a digit length: `generic`, `international`, `secrets`, `secrets-extended`,
`network`, `crypto`. Their shapes carry a prefix, a separator or an alphabet
that sets them apart, so they add to any country.

The composition check replays the examples of every kept pattern against the
flattened set, so a collision between two countries fails publication rather
than arriving at a user.

## Resolving a configuration

A configuration resolves into an ordered list of named detectors and a table of
stages, with the same discipline:

- The parents' detectors, in the order of the `[[extends]]`, then the
  configuration's own. A name present twice is an error: exclude it in the
  parent (`detector:<name>`) or rename.
- `label:<LABEL>` removes a label from the regex detectors inherited from that
  parent. The label must exist in the parent; emptying a detector completely is
  an error, in which case exclude the detector.
- A stage written in the child replaces the parent's stage wholesale, with no
  key-by-key merge: merging `threshold` or `labels` would produce a
  configuration nobody wrote. Two parents providing the same stage is an error,
  settled with `stage:<section>`.
- A regex detector listing several `groups` merges them with the group rules: a
  shared label is an error, except a diamond.

## Rendering

Rendering produces a piighost file. A single detector is written as it is,
several become a `composite` in order. Two forms:

- **flattened**, the default: each regex detector receives `patterns = { LABEL =
  '...' }` in the resolved order. The file works offline, on any piighost
  version that accepts its sections, with no catalog support.
- **referenced** (`keep_refs`): `catalogs = ["catalog:piighost/fr:3fa9c2e1"]`,
  for a piighost that resolves them itself, which 2.0 does; see
  [library-support.md](library-support.md).

Every rendered configuration is validated by the installed piighost's
`PipelineConfig`, without building a component: no model loads.

## Checks

`python -m backend.hub check` runs, on the working heads:

| Check | Subject | Fails when |
|---|---|---|
| Structure | manifests | unknown key, malformed name or label, uncompilable regex, tag outside the vocabulary, missing or repeated `value`, `exclude` together with `only` |
| Examples | patterns | a `match` is not detected as its value, a `no_match` is |
| Resilience | patterns | a value wrapped in punctuation is not detected alone and whole |
| Composition | groups, configurations | an example of a kept pattern is no longer detected under its label once composed, stolen by a neighbour on the same span or swallowed by a wider one |
| Backtracking bound | patterns | a 100,000 character adversarial scan exceeds 0.25 s, or does not finish in 5 s (the process is killed) |
| Rendering | configurations | piighost rejects the rendered pipeline, or the configuration declares a piighost range excluding the installed version |
| Store | commits | a snapshot no longer matches its digest |
| Tags | pointers | a tag points at an unknown commit |
| Recording | heads | a head is not recorded (`record` fixes it) |

Every check runs with the real piighost components, `RegexDetector` and
`ConfidenceOverlapResolver`, never a reimplementation.
