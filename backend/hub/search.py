"""Searching and browsing the registry.

The index is built once at startup from the frozen heads, because a registry is
read far more often than it is published and nothing about it changes between
two requests. Matching is a plain scored substring search over the fields a
visitor would type: the key, the labels, the description, the tags. A few dozen
to a few thousand objects do not justify a search engine, and adding one would
put a service between the site and data it already holds in memory.
"""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field

from backend.hub.refs import strip_scheme
from backend.hub.registry import Registry
from backend.hub.store import Snapshot


def fold(text: str) -> str:
    """Lowercase and strip accents, so `notariat` finds `Notariat`."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass(slots=True)
class Entry:
    """One object in the index, with everything the list view displays."""

    key: str
    kind: str
    name: str
    namespace: str
    commit: str
    tags: list[str]
    labels: list[str]
    description: dict[str, str] = field(default_factory=dict)
    updated_at: str | None = None
    """When the newest commit was recorded; None while the head is unrecorded."""
    commits: int = 0
    haystack: str = ""
    used_by: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Facet:
    """A tag and how many objects of the current result set carry it."""

    tag: str
    kind: str
    count: int


class Index:
    """An in-memory index of the registry heads."""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self.entries: dict[str, Entry] = {}
        self._build()

    def _build(self) -> None:
        from backend.hub.resolve import resolve_config, resolve_labels

        for key, head in sorted(self.registry.heads.items()):
            labels: list[str] = []
            try:
                if head.kind == "config":
                    resolved = resolve_config(self.registry, head)
                    labels = sorted(
                        {
                            label
                            for detector in resolved.detectors
                            if detector.labels is not None
                            for label in detector.labels.labels
                        }
                    )
                else:
                    labels = list(resolve_labels(self.registry, head).labels)
            except Exception:  # noqa: BLE001 - an unresolvable head still lists
                labels = []
            description = head.content.get("description", {})
            history = self.registry.history(key)
            entry = Entry(
                key=key,
                kind=head.kind,
                name=head.name,
                namespace=head.namespace,
                commit=head.short,
                tags=list(head.content.get("tags", [])),
                labels=labels,
                description={
                    "en": description.get("en") or "",
                    "fr": description.get("fr") or "",
                },
                updated_at=next(
                    (s.recorded_at for s in history if s.recorded_at), None
                ),
                commits=len(history),
            )
            entry.haystack = fold(
                " ".join(
                    [
                        key,
                        head.name,
                        " ".join(entry.tags),
                        " ".join(labels),
                        # `or ""`, not a default: a manifest that declares
                        # `fr = ` with nothing, or omits it since French is
                        # optional, carries an explicit None.
                        description.get("en") or "",
                        description.get("fr") or "",
                    ]
                )
            )
            self.entries[key] = entry
        self._link()

    def _link(self) -> None:
        """Record, for each object, which objects reference it."""
        for key, head in self.registry.heads.items():
            for child in _referenced(head):
                entry = self.entries.get(child)
                if entry is not None and key not in entry.used_by:
                    entry.used_by.append(key)
        for entry in self.entries.values():
            entry.used_by.sort()

    def search(
        self,
        query: str = "",
        *,
        kind: Sequence[str] | None = None,
        tags: list[str] | None = None,
        label: str | None = None,
        sort: str = "relevance",
        pulls: dict[str, int] | None = None,
    ) -> list[Entry]:
        """Return matching entries, ordered by ``sort``, then by key.

        Tags are combined with AND: picking two facets narrows, which is what a
        visitor expects from a facet list and what makes the counts meaningful.
        ``relevance`` is the match score, which is flat without a query, so the
        other orders exist for browsing: ``updated`` newest first, ``used`` most
        referenced first, ``labels`` widest first, ``pulls`` most fetched first,
        ``name`` alphabetical.

        ``kind`` is a list because the catalog asks for several at once: the
        site lists patterns and groups together and keeps the piighost configs
        on their own page. An empty or absent list means every kind.

        ``pulls`` comes from the caller rather than the index because it changes
        with every request while the index is built once at startup.
        """
        needle = fold(query.strip())
        wanted = set(tags or [])
        kinds = set(kind or ())
        results: list[tuple[int, str, Entry]] = []
        for entry in self.entries.values():
            if kinds and entry.kind not in kinds:
                continue
            if wanted and not wanted.issubset(entry.tags):
                continue
            if label is not None and label not in entry.labels:
                continue
            score = self._score(entry, needle)
            if score is None:
                continue
            results.append((-score, entry.key, entry))
        order = _sort_key(sort, pulls or {})
        return [entry for _, _, entry in sorted(results, key=order)]

    @staticmethod
    def _score(entry: Entry, needle: str) -> int | None:
        if not needle:
            return 0
        if needle == fold(entry.name) or needle == fold(entry.key):
            return 100
        if fold(entry.name).startswith(needle):
            return 50
        if any(needle == fold(label) for label in entry.labels):
            return 40
        if any(needle in fold(label) for label in entry.labels):
            return 20
        if needle in entry.haystack:
            return 10
        return None

    def facets(self, entries: list[Entry]) -> list[Facet]:
        """Count each tag over a result set, most frequent first."""
        counts: dict[str, int] = {}
        for entry in entries:
            for tag in entry.tags:
                counts[tag] = counts.get(tag, 0) + 1
        vocabulary = self.registry.vocabulary
        return sorted(
            (
                Facet(
                    tag=tag,
                    kind=vocabulary[tag].kind if tag in vocabulary else "",
                    count=count,
                )
                for tag, count in counts.items()
            ),
            key=lambda facet: (-facet.count, facet.kind, facet.tag),
        )

    def labels(self) -> dict[str, list[str]]:
        """Every label the registry can emit, mapped to the patterns defining it."""
        found: dict[str, list[str]] = {}
        for key, head in self.registry.heads.items():
            if head.kind == "pattern":
                found.setdefault(head.content["label"], []).append(key)
        return {label: sorted(keys) for label, keys in sorted(found.items())}


SORTS = ("relevance", "updated", "used", "labels", "pulls", "name")


def _sort_key(sort: str, pulls: dict[str, int]):
    if sort == "updated":
        return lambda item: (
            item[2].updated_at is None,
            _descending(item[2].updated_at or ""),
            item[1],
        )
    if sort == "used":
        return lambda item: (-len(item[2].used_by), item[1])
    if sort == "labels":
        return lambda item: (-len(item[2].labels), item[1])
    if sort == "pulls":
        return lambda item: (-pulls.get(item[1], 0), item[1])
    if sort == "name":
        return lambda item: (item[2].name, item[1])
    return lambda item: (item[0], item[1])


def _descending(text: str) -> str:
    """Invert a string's sort order, so an ISO date sorts newest first."""
    return "".join(chr(0x10FFFF - ord(c)) for c in text)


def _referenced(head: Snapshot) -> list[str]:
    content = head.content
    keys: list[str] = []
    for source in content.get("sources", []):
        keys.append(_key(source["ref"]))
    for parent in content.get("extends", []):
        keys.append(_key(parent["ref"]))
    for detector in content.get("detectors", []):
        for group in detector.get("groups", []):
            keys.append(_key(group["ref"]))
    return keys


def _key(ref_text: str) -> str:
    body = strip_scheme(ref_text)
    return body.split(":", 1)[0]
