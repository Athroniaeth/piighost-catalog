"""Load a registry directory, validate its manifests, and freeze its heads.

Loading is strict: every structural problem across the tree is collected and
reported at once as a ManifestError, so an author fixes a batch, not one line per
run. Freezing turns each working-tree manifest into its head snapshot, resolving
the references it carries to commits, in dependency order, refusing cycles.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import msgspec

from backend.hub.errors import ManifestError, RefError, ResolutionError
from backend.hub.manifests import (
    FORBIDDEN_SECTIONS,
    LABEL,
    SCHEMA_VERSION,
    STAGE_SECTIONS,
    ConfigManifest,
    GroupManifest,
    LocalizedText,
    PatternManifest,
    TagDefinition,
    TagPointers,
    Vocabulary,
    load_toml,
)
from backend.hub.refs import LATEST, Ref, is_valid_name, is_valid_tag, parse_ref
from backend.hub.samples import Sample, load_samples
from backend.hub.store import CommitStore, Kind, Snapshot

REGISTRY_DIR_ENV_VAR = "HUB_REGISTRY_DIR"
"""Names the directory to load; the routes read it, this is only for the message."""

VOCABULARY_FILE = "vocabulary.toml"
POINTERS_FILE = "tags.toml"
KIND_DIRS: dict[Kind, str] = {
    "pattern": "patterns",
    "group": "groups",
    "config": "configs",
}
MANIFEST_FILES: dict[Kind, str] = {
    "pattern": "pattern.toml",
    "group": "group.toml",
    "config": "config.toml",
}
EXCLUDE_PREFIXES = ("detector:", "label:", "stage:")

Manifest = PatternManifest | GroupManifest | ConfigManifest


@dataclass(slots=True)
class HubObject:
    """One manifest in the working tree, with its tag pointers."""

    kind: Kind
    namespace: str
    name: str
    path: Path
    manifest: Manifest
    pointers: TagPointers = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.namespace}/{self.name}"

    def references(self) -> list[str]:
        """The reference strings this manifest carries, in order."""
        manifest = self.manifest
        if isinstance(manifest, GroupManifest):
            return [source.ref for source in manifest.sources]
        if isinstance(manifest, ConfigManifest):
            refs = [parent.ref for parent in manifest.extends]
            for detector in manifest.detectors:
                refs.extend(detector.get("groups", []))
            return refs
        return []


class Registry:
    """A loaded registry: vocabulary, working-tree objects, commit store, heads."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.vocabulary: Vocabulary = {}
        self.objects: dict[str, HubObject] = {}
        self.samples: dict[str, Sample] = {}
        self.store = CommitStore(root)
        self.heads: dict[str, Snapshot] = {}

    # ------------------------------------------------------------------ loading

    @classmethod
    def load(cls, root: Path) -> Registry:
        """Load and validate a registry, then freeze every head.

        Raises:
            ManifestError: With every structural problem found, joined.
            ResolutionError: If references cannot be frozen (cycle, unknown).
        """
        if not root.is_dir():
            raise ManifestError(
                f"no registry at {root}. Set {REGISTRY_DIR_ENV_VAR} to the directory "
                f"holding vocabulary.toml, patterns/, groups/ and configs/ — the "
                f"Docker image ships it at /app/registry."
            )
        registry = cls(root)
        problems: list[str] = []
        registry._load_vocabulary(problems)
        for kind in KIND_DIRS:
            registry._load_kind(kind, problems)
        registry.samples = load_samples(root, set(registry.vocabulary), problems)
        if problems:
            raise ManifestError("\n".join(problems))
        registry.freeze()
        return registry

    def _load_vocabulary(self, problems: list[str]) -> None:
        path = self.root / VOCABULARY_FILE
        try:
            self.vocabulary = load_toml(path, dict[str, TagDefinition])
        except ManifestError as exc:
            problems.append(str(exc))
            return
        for tag, definition in self.vocabulary.items():
            if not is_valid_name(tag):
                problems.append(f"{path}: tag {tag!r} is not kebab-case")
            if not definition.kind:
                problems.append(f"{path}: tag {tag!r} has no kind")

    def _load_kind(self, kind: Kind, problems: list[str]) -> None:
        base = self.root / KIND_DIRS[kind]
        if not base.is_dir():
            return
        for path in sorted(base.glob(f"*/*/{MANIFEST_FILES[kind]}")):
            namespace = path.parent.parent.name
            name = path.parent.name
            try:
                obj = self._load_object(kind, namespace, name, path)
            except ManifestError as exc:
                problems.append(str(exc))
                continue
            problems.extend(f"{path}: {p}" for p in self._validate(obj))
            if obj.key in self.objects:
                problems.append(f"{path}: {obj.key} is defined twice")
            self.objects[obj.key] = obj

    def _load_object(
        self, kind: Kind, namespace: str, name: str, path: Path
    ) -> HubObject:
        schema: type[Manifest]
        if kind == "pattern":
            schema = PatternManifest
        elif kind == "group":
            schema = GroupManifest
        else:
            schema = ConfigManifest
        manifest = load_toml(path, schema)
        pointers_path = path.parent / POINTERS_FILE
        pointers: TagPointers = {}
        if pointers_path.is_file():
            pointers = load_toml(pointers_path, dict[str, str])
        return HubObject(kind, namespace, name, path, manifest, pointers)

    def _validate(self, obj: HubObject) -> list[str]:
        """Structural rules a schema cannot express."""
        problems: list[str] = []
        manifest = obj.manifest
        body: Any = getattr(manifest, obj.kind)

        if manifest.schema_version != SCHEMA_VERSION:
            problems.append(f"schema_version must be {SCHEMA_VERSION}")
        if not is_valid_name(obj.namespace):
            problems.append(f"namespace {obj.namespace!r} is not kebab-case")
        if body.name != obj.name:
            problems.append(f"name {body.name!r} must equal its directory {obj.name!r}")
        if not is_valid_name(body.name):
            problems.append(f"name {body.name!r} is not kebab-case")
        for tag in body.tags:
            if tag not in self.vocabulary:
                problems.append(
                    f"unknown tag {tag!r}, add it to {VOCABULARY_FILE} first"
                )
        for tag, commit in obj.pointers.items():
            if not is_valid_tag(tag):
                problems.append(
                    f"{POINTERS_FILE}: {tag!r} is not a valid tag (kebab-case, "
                    f"not {LATEST!r}, not hex-only)"
                )
            if not re.fullmatch(r"[0-9a-f]{8}", commit):
                problems.append(f"{POINTERS_FILE}: {tag} = {commit!r} is not a commit")
        for text in obj.references():
            try:
                parse_ref(text)
            except RefError as exc:
                problems.append(str(exc))

        if isinstance(manifest, PatternManifest):
            problems.extend(self._validate_pattern(manifest))
        elif isinstance(manifest, GroupManifest):
            problems.extend(self._validate_group(manifest))
        else:
            problems.extend(self._validate_config(manifest))
        return problems

    @staticmethod
    def _validate_pattern(manifest: PatternManifest) -> list[str]:
        problems: list[str] = []
        pattern = manifest.pattern
        if not LABEL.fullmatch(pattern.label):
            problems.append(f"label {pattern.label!r} must be UPPER_SNAKE")
        try:
            re.compile(pattern.regex, re.ASCII)
        except re.error as exc:
            problems.append(f"regex does not compile: {exc}")
        if not manifest.examples.match:
            problems.append("at least one [[examples.match]] is required")
        if not manifest.examples.no_match:
            problems.append("at least one [[examples.no_match]] is required")
        for example in manifest.examples.match:
            if example.text.count(example.value) != 1:
                problems.append(
                    f"match example value {example.value!r} must appear exactly "
                    f"once in its text"
                )
        return problems

    @staticmethod
    def _validate_group(manifest: GroupManifest) -> list[str]:
        problems: list[str] = []
        if not manifest.sources:
            problems.append("a group needs at least one [[sources]] entry")
        for source in manifest.sources:
            if source.exclude and source.only:
                problems.append(f"source {source.ref}: exclude and only are exclusive")
        return problems

    @staticmethod
    def _validate_config(manifest: ConfigManifest) -> list[str]:
        problems: list[str] = []
        names: set[str] = set()
        for detector in manifest.detectors:
            name = detector.get("name")
            if not isinstance(name, str) or not is_valid_name(name):
                problems.append(f"detector {detector!r} needs a kebab-case name")
                continue
            if name in names:
                problems.append(f"detector {name!r} is declared twice")
            names.add(name)
            if not isinstance(detector.get("type"), str):
                problems.append(f"detector {name!r} needs a type")
            if detector.get("type") == "regex":
                extra = set(detector) - {"name", "type", "groups"}
                if extra:
                    problems.append(
                        f"regex detector {name!r}: only groups is allowed, not "
                        f"{sorted(extra)}; inline patterns bypass the tested patterns"
                    )
                if not detector.get("groups"):
                    problems.append(f"regex detector {name!r} needs at least one group")
            elif "groups" in detector:
                problems.append(f"detector {name!r}: groups is only for type regex")
        for section in manifest.stages:
            if section in FORBIDDEN_SECTIONS:
                problems.append(
                    f"stage {section!r} is a deployment concern, not shared"
                )
            elif section not in STAGE_SECTIONS:
                problems.append(f"unknown stage {section!r}")
        for parent in manifest.extends:
            for item in parent.exclude:
                if not item.startswith(EXCLUDE_PREFIXES):
                    problems.append(
                        f"extends {parent.ref}: exclude {item!r} must start with one of "
                        f"{', '.join(EXCLUDE_PREFIXES)}"
                    )
        if not manifest.detectors and not manifest.extends:
            problems.append("a config needs a detector or a parent")
        return problems

    # ----------------------------------------------------------------- freezing

    def freeze(self) -> None:
        """Compute the head snapshot of every object, dependencies first."""
        self.heads = {}
        for key in sorted(self.objects):
            self._head(key, visiting=[])

    def _head(self, key: str, visiting: list[str]) -> Snapshot:
        head = self.heads.get(key)
        if head is not None:
            return head
        if key in visiting:
            chain = " -> ".join([*visiting[visiting.index(key) :], key])
            raise ResolutionError(f"reference cycle: {chain}")
        obj = self.objects[key]
        visiting.append(key)
        content = self._freeze_content(obj, visiting)
        visiting.pop()
        head = Snapshot.freeze(content)
        self.heads[key] = head
        return head

    def _pin(self, text: str, visiting: list[str]) -> str:
        """Resolve a written reference to the commit it designates today."""
        return self.resolve(parse_ref(text), visiting).short

    def resolve(self, ref: Ref, visiting: list[str] | None = None) -> Snapshot:
        """Return the snapshot a reference designates.

        ``latest`` and the bare form designate the working-tree head. A commit
        designates a recorded snapshot, or the head when it is the head's own
        commit. A tag reads the object's pointers.

        Raises:
            ResolutionError: For an unknown object, tag or commit.
        """
        visiting = visiting if visiting is not None else []
        obj = self.objects.get(ref.key)
        if ref.selector == LATEST:
            if obj is None:
                raise ResolutionError(f"unknown object {ref.key}")
            return self._recorded_or(self._head(ref.key, visiting))
        if ref.is_commit:
            short = ref.selector
        else:
            if obj is None:
                raise ResolutionError(f"unknown object {ref.key}")
            pointer = obj.pointers.get(ref.selector)
            if pointer is None:
                raise ResolutionError(f"{ref.key} has no tag {ref.selector!r}")
            short = pointer
        if obj is not None:
            head = self._head(ref.key, visiting)
            if head.short == short:
                return self._recorded_or(head)
        recorded = self.store.get(ref.key, short)
        if recorded is None:
            raise ResolutionError(f"{ref.key}:{short} is not a recorded commit")
        return recorded

    def _freeze_content(self, obj: HubObject, visiting: list[str]) -> dict[str, Any]:
        manifest = obj.manifest
        base: dict[str, Any] = {
            "kind": obj.kind,
            "namespace": obj.namespace,
            "name": obj.name,
            "schema_version": manifest.schema_version,
        }
        if isinstance(manifest, PatternManifest):
            pattern = manifest.pattern
            base.update(
                {
                    "label": pattern.label,
                    "regex": pattern.regex,
                    "description": msgspec.to_builtins(pattern.description),
                    "tags": list(pattern.tags),
                    "resilience": pattern.resilience,
                    "examples": msgspec.to_builtins(manifest.examples),
                    "redos": msgspec.to_builtins(manifest.redos),
                }
            )
            return base
        if isinstance(manifest, GroupManifest):
            base.update(
                {
                    "description": msgspec.to_builtins(manifest.group.description),
                    "tags": list(manifest.group.tags),
                    "sources": [
                        {
                            "ref": source.ref,
                            "commit": self._pin(source.ref, visiting),
                            "exclude": list(source.exclude),
                            "only": list(source.only),
                        }
                        for source in manifest.sources
                    ],
                }
            )
            return base
        detectors: list[dict[str, Any]] = []
        for detector in manifest.detectors:
            frozen = dict(detector)
            if "groups" in frozen:
                frozen["groups"] = [
                    {"ref": text, "commit": self._pin(text, visiting)}
                    for text in detector["groups"]
                ]
            detectors.append(frozen)
        base.update(
            {
                "description": msgspec.to_builtins(manifest.config.description),
                "tags": list(manifest.config.tags),
                "piighost": manifest.config.piighost,
                "extends": [
                    {
                        "ref": parent.ref,
                        "commit": self._pin(parent.ref, visiting),
                        "exclude": list(parent.exclude),
                    }
                    for parent in manifest.extends
                ],
                "detectors": detectors,
                "stages": manifest.stages,
            }
        )
        return base

    # ---------------------------------------------------------------- queries

    def snapshot(self, key: str, short: str) -> Snapshot:
        """Return a snapshot by commit, from the heads or the store."""
        head = self.heads.get(key)
        if head is not None and head.short == short:
            return self._recorded_or(head)
        recorded = self.store.get(key, short)
        if recorded is None:
            raise ResolutionError(f"{key}:{short} is not a recorded commit")
        return recorded

    def _recorded_or(self, head: Snapshot) -> Snapshot:
        """The recorded copy of a head when there is one, else the head itself.

        The two carry the same content and digest; only the recorded one knows
        when it was published. Serving the in-memory head for `latest` made the
        API call the current commit unrecorded while listing its date one line
        below, in the history.
        """
        return self.store.get(head.key, head.short) or head

    def history(self, key: str) -> list[Snapshot]:
        """Recorded commits of an object, newest first, the head first if unrecorded."""
        recorded = self.store.history(key)
        head = self.heads.get(key)
        if head is not None and not any(s.short == head.short for s in recorded):
            return [head, *recorded]
        return recorded

    def title_of(self, key: str) -> LocalizedText | None:
        """What a reader calls an object, `SIRET (France)` for `piighost/fr-siret`.

        The page headings and titles lead with it, because nobody searches for
        `fr-siret`. It is written mid-sentence, `phone number (France)`: a
        heading capitalises its first letter, a title puts it after "Regex".

        Read from the working tree and left out of the frozen content, like a
        tag's label in vocabulary.toml. It names the object without changing
        what it detects, so renaming a page must not mint a commit, move
        `latest` or change a digest someone pinned. An object deleted from the
        working tree, or written without one, has none.
        """
        obj = self.objects.get(key)
        if obj is None:
            return None
        return getattr(obj.manifest, obj.kind).title

    def tags_of(self, key: str) -> dict[str, str]:
        """Tag pointers of an object, ``latest`` included."""
        obj = self.objects.get(key)
        tags: dict[str, str] = {}
        if obj is not None:
            tags.update(obj.pointers)
            tags[LATEST] = self.heads[key].short
        return tags
