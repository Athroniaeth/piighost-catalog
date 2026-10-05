"""Resolve snapshots into flat, ordered label sets and pipeline pieces.

Three rules, nothing else. A label reached from two sources is an error the
author settles with ``exclude`` or ``only`` in one source's block, unless both
sources are the very same pattern commit (a harmless diamond). ``exclude`` and
``only`` must name labels the source actually provides, so a typo is caught. The
order of sources is the order of insertion in the detector, hence the tie-break
between two patterns matching the same span: piighost's resolver keeps the first
inserted, and the catalog adds no rule of its own.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from backend.hub.errors import ResolutionError
from backend.hub.refs import strip_scheme
from backend.hub.registry import Registry
from backend.hub.store import Snapshot


@dataclass(frozen=True, slots=True)
class ResolvedLabel:
    """One label of a flattened set, with where it came from."""

    label: str
    regex: str
    pattern: str
    """The pattern commit, ``namespace/name:short``."""
    via: tuple[str, ...]
    """The group commits traversed to reach it, outermost first."""


@dataclass(slots=True)
class ResolvedLabels:
    """An ordered label set: what a regex detector receives."""

    ref: str
    labels: dict[str, ResolvedLabel] = field(default_factory=dict)
    patterns: dict[str, Snapshot] = field(default_factory=dict)
    """Every pattern snapshot that contributed, by its ``ns/name:short``."""

    def regexes(self) -> dict[str, str]:
        """The ``label -> regex`` mapping, in insertion order."""
        return {label: entry.regex for label, entry in self.labels.items()}

    def add(self, entry: ResolvedLabel, snapshot: Snapshot) -> None:
        existing = self.labels.get(entry.label)
        if existing is not None:
            if existing.pattern == entry.pattern:
                return
            raise ResolutionError(
                f"{self.ref}: label {entry.label} comes from both "
                f"{existing.pattern} (via {' > '.join(existing.via) or 'direct'}) and "
                f"{entry.pattern} (via {' > '.join(entry.via) or 'direct'}); "
                f"exclude it from one source"
            )
        self.labels[entry.label] = entry
        self.patterns.setdefault(entry.pattern, snapshot)

    def without(self, labels: set[str]) -> ResolvedLabels:
        kept = ResolvedLabels(ref=self.ref)
        for label, entry in self.labels.items():
            if label not in labels:
                kept.labels[label] = entry
                kept.patterns.setdefault(entry.pattern, self.patterns[entry.pattern])
        return kept


def resolve_labels(
    registry: Registry, snapshot: Snapshot, via: tuple[str, ...] = ()
) -> ResolvedLabels:
    """Flatten a pattern or group snapshot into its ordered label set."""
    resolved = ResolvedLabels(ref=snapshot.ref)
    content = snapshot.content

    if snapshot.kind == "pattern":
        entry = ResolvedLabel(
            label=content["label"],
            regex=content["regex"],
            pattern=snapshot.ref,
            via=via,
        )
        resolved.add(entry, snapshot)
        return resolved

    if snapshot.kind != "group":
        raise ResolutionError(f"{snapshot.ref} is a config, not a label source")

    return resolve_sources(registry, content["sources"], resolved, via)


def _head_of(registry: Registry, key: str) -> Snapshot:
    head = registry.heads.get(key)
    if head is None:
        raise ResolutionError(f"unknown object {key}")
    return head


def resolve_sources(
    registry: Registry,
    sources: Iterable[Mapping[str, Any]],
    into: ResolvedLabels,
    via: tuple[str, ...] = (),
) -> ResolvedLabels:
    """Merge a list of sources into one ordered label set.

    Split out of the group branch above so that a group which is not in the
    registry yet, the one being written on the contribution page, is resolved by
    this code and not by a second reading of the same rules somewhere else. A
    label arriving twice is an error here, and that is the rule the whole
    registry rests on.
    """
    for source in sources:
        key = _key_of(source["ref"])
        commit = source.get("commit")
        # A frozen manifest pins every source; a draft from the contribution
        # page has not been frozen yet, so it means the head.
        child = registry.snapshot(key, commit) if commit else _head_of(registry, key)
        child_labels = resolve_labels(registry, child, (*via, into.ref))
        provided = set(child_labels.labels)
        exclude = set(source.get("exclude") or ())
        only = set(source.get("only") or ())
        for name in sorted((exclude | only) - provided):
            raise ResolutionError(
                f"{into.ref}: source {child.ref} provides no label {name}; "
                f"it provides {sorted(provided)}"
            )
        dropped = exclude if exclude else (provided - only if only else set())
        for entry in child_labels.without(dropped).labels.values():
            into.add(entry, child_labels.patterns[entry.pattern])
    return into


@dataclass(slots=True)
class ResolvedDetector:
    """A detector of a rendered pipeline."""

    name: str
    spec: dict[str, Any]
    """The piighost detector config keys, without ``name`` and ``groups``."""
    labels: ResolvedLabels | None = None
    """The flattened regex labels, for a regex detector."""
    groups: list[str] = field(default_factory=list)
    """The group commits a regex detector was built from."""


@dataclass(slots=True)
class ResolvedConfig:
    """A config flattened through its parents, ready to render."""

    ref: str
    snapshot: Snapshot
    piighost: str
    detectors: list[ResolvedDetector] = field(default_factory=list)
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)

    def regex_detectors(self) -> list[ResolvedDetector]:
        return [d for d in self.detectors if d.labels is not None]


def resolve_config(registry: Registry, snapshot: Snapshot) -> ResolvedConfig:
    """Flatten a config snapshot: parents in order, then its own pieces."""
    if snapshot.kind != "config":
        raise ResolutionError(f"{snapshot.ref} is not a config")
    content = snapshot.content
    resolved = ResolvedConfig(
        ref=snapshot.ref, snapshot=snapshot, piighost=content.get("piighost", "")
    )

    for parent_ref in content["extends"]:
        parent_snapshot = registry.snapshot(
            _key_of(parent_ref["ref"]), parent_ref["commit"]
        )
        parent = resolve_config(registry, parent_snapshot)
        _inherit(resolved, parent, parent_ref["exclude"])

    for detector in content["detectors"]:
        resolved_detector = _own_detector(registry, snapshot, detector)
        if any(d.name == resolved_detector.name for d in resolved.detectors):
            raise ResolutionError(
                f"{snapshot.ref}: detector {resolved_detector.name!r} already comes "
                f"from a parent; exclude it there or rename this one"
            )
        resolved.detectors.append(resolved_detector)

    # A stage written in the child replaces the parent's wholesale: a key-by-key
    # merge would produce a stage nobody wrote.
    for section, stage in content["stages"].items():
        resolved.stages[section] = dict(stage)
    return resolved


def _inherit(
    resolved: ResolvedConfig, parent: ResolvedConfig, exclude: list[str]
) -> None:
    detectors_out = {item[9:] for item in exclude if item.startswith("detector:")}
    labels_out = {item[6:] for item in exclude if item.startswith("label:")}
    stages_out = {item[6:] for item in exclude if item.startswith("stage:")}

    parent_detectors = {d.name for d in parent.detectors}
    for name in sorted(detectors_out - parent_detectors):
        raise ResolutionError(
            f"{resolved.ref}: {parent.ref} has no detector {name!r}; "
            f"it has {sorted(parent_detectors)}"
        )
    for section in sorted(stages_out - set(parent.stages)):
        raise ResolutionError(
            f"{resolved.ref}: {parent.ref} has no stage {section!r}; "
            f"it has {sorted(parent.stages)}"
        )
    parent_labels: set[str] = set()
    for detector in parent.regex_detectors():
        if detector.labels is not None:
            parent_labels |= set(detector.labels.labels)
    for label in sorted(labels_out - parent_labels):
        raise ResolutionError(
            f"{resolved.ref}: {parent.ref} provides no label {label}; "
            f"it provides {sorted(parent_labels)}"
        )

    for detector in parent.detectors:
        if detector.name in detectors_out:
            continue
        if any(d.name == detector.name for d in resolved.detectors):
            raise ResolutionError(
                f"{resolved.ref}: detector {detector.name!r} comes from two parents; "
                f"exclude it from one"
            )
        labels = detector.labels
        if labels is not None and labels_out:
            labels = labels.without(labels_out)
            if not labels.labels:
                raise ResolutionError(
                    f"{resolved.ref}: excluding {sorted(labels_out)} empties detector "
                    f"{detector.name!r}; exclude the detector instead"
                )
        resolved.detectors.append(
            ResolvedDetector(
                detector.name, dict(detector.spec), labels, list(detector.groups)
            )
        )

    for section, stage in parent.stages.items():
        if section in stages_out:
            continue
        if section in resolved.stages:
            raise ResolutionError(
                f"{resolved.ref}: stage {section!r} comes from two parents; "
                f"exclude it from one"
            )
        resolved.stages[section] = dict(stage)


def _own_detector(
    registry: Registry, snapshot: Snapshot, detector: dict[str, Any]
) -> ResolvedDetector:
    spec = {k: v for k, v in detector.items() if k not in {"name", "groups"}}
    name = detector["name"]
    if detector.get("type") != "regex":
        return ResolvedDetector(name=name, spec=spec)

    labels = ResolvedLabels(ref=f"{snapshot.ref}#{name}")
    groups: list[str] = []
    for group_ref in detector["groups"]:
        group = registry.snapshot(_key_of(group_ref["ref"]), group_ref["commit"])
        groups.append(group.ref)
        for entry in resolve_labels(registry, group).labels.values():
            labels.add(
                entry,
                registry.snapshot(
                    _key_of(entry.pattern), entry.pattern.rsplit(":", 1)[1]
                ),
            )
    return ResolvedDetector(name=name, spec=spec, labels=labels, groups=groups)


def _key_of(ref_text: str) -> str:
    """``ns/name`` of a written reference, whatever its selector."""
    body = strip_scheme(ref_text)
    return body.split(":", 1)[0]
