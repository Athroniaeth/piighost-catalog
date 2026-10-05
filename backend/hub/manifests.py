"""Manifest schemas, one per object kind, decoded from TOML with msgspec.

Unknown keys are rejected so a typo fails at load time instead of being ignored.
Everything that is not plain structure (regex validity, tag vocabulary, naming
rules, reference existence) is checked by the registry loader, which has the
context these schemas lack.
"""

import re
from pathlib import Path
from typing import Any

import msgspec

from backend.hub.errors import ManifestError

SCHEMA_VERSION = 1

LABEL = re.compile(r"^[A-Z][A-Z0-9_]*$")
"""A detector label, as piighost emits it."""


class LocalizedText(msgspec.Struct, forbid_unknown_fields=True):
    """A short text, in English and optionally in French.

    The registry was bilingual because the site was, and the site is not any
    more. The objects written while it was keep their French, which costs
    nothing and would be a shame to delete; a new one is not asked for it.
    """

    en: str
    fr: str | None = None


class MatchExample(msgspec.Struct, forbid_unknown_fields=True):
    """A text the pattern must match, and the exact value it must capture."""

    text: str
    value: str


class NoMatchExample(msgspec.Struct, forbid_unknown_fields=True):
    """A look-alike text the pattern must leave alone."""

    text: str


class Examples(msgspec.Struct, forbid_unknown_fields=True):
    """The golden examples of a pattern."""

    match: list[MatchExample] = msgspec.field(default_factory=list)
    no_match: list[NoMatchExample] = msgspec.field(default_factory=list)


class RedosRecipe(msgspec.Struct, forbid_unknown_fields=True):
    """An adversarial text recipe: a valid prefix, a repeated ambiguous fragment,
    and an ending that denies the match. Used to bound backtracking."""

    prefix: str
    filler: str
    suffix: str


class PatternBody(msgspec.Struct, forbid_unknown_fields=True):
    """The ``[pattern]`` table."""

    name: str
    label: str
    regex: str
    description: LocalizedText
    tags: list[str] = msgspec.field(default_factory=list)
    resilience: bool = True


class PatternManifest(msgspec.Struct, forbid_unknown_fields=True):
    """``pattern.toml``: one regex, one label, its examples."""

    schema_version: int
    pattern: PatternBody
    examples: Examples = msgspec.field(default_factory=Examples)
    redos: RedosRecipe | None = None


class Source(msgspec.Struct, forbid_unknown_fields=True):
    """One entry of a group's ordered ``[[sources]]`` list."""

    ref: str
    exclude: list[str] = msgspec.field(default_factory=list)
    only: list[str] = msgspec.field(default_factory=list)


class GroupBody(msgspec.Struct, forbid_unknown_fields=True):
    """The ``[group]`` table."""

    name: str
    description: LocalizedText
    tags: list[str] = msgspec.field(default_factory=list)


class GroupManifest(msgspec.Struct, forbid_unknown_fields=True):
    """``group.toml``: an ordered composition of patterns and groups."""

    schema_version: int
    group: GroupBody
    sources: list[Source] = msgspec.field(default_factory=list)


class Extends(msgspec.Struct, forbid_unknown_fields=True):
    """One entry of a config's ordered ``[[extends]]`` list.

    ``exclude`` entries are prefixed: ``detector:<name>``, ``label:<LABEL>`` or
    ``stage:<section>``.
    """

    ref: str
    exclude: list[str] = msgspec.field(default_factory=list)


class ConfigBody(msgspec.Struct, forbid_unknown_fields=True):
    """The ``[config]`` table."""

    name: str
    description: LocalizedText
    tags: list[str] = msgspec.field(default_factory=list)
    piighost: str = ""


class ConfigManifest(msgspec.Struct, forbid_unknown_fields=True):
    """``config.toml``: detectors, stages, and the configs it extends.

    A detector is a piighost detector config plus a ``name``. A regex detector
    carries ``groups`` (catalog references) and no inline patterns, so every regex
    reaching a config went through a tested pattern. Stages are piighost sections
    passed through as is; ``memory`` and ``token_memo_ttl`` are deployment
    concerns and are refused.
    """

    schema_version: int
    config: ConfigBody
    extends: list[Extends] = msgspec.field(default_factory=list)
    detectors: list[dict[str, Any]] = msgspec.field(default_factory=list)
    stages: dict[str, dict[str, Any]] = msgspec.field(default_factory=dict)


class TagDefinition(msgspec.Struct, forbid_unknown_fields=True):
    """One entry of ``vocabulary.toml``."""

    kind: str
    label: LocalizedText


Vocabulary = dict[str, TagDefinition]
TagPointers = dict[str, str]
"""``tags.toml`` next to a manifest: tag name to commit."""

STAGE_SECTIONS = frozenset(
    {
        "linker",
        "anonymizer",
        "overlap_resolver",
        "expander",
        "entity_resolver",
        "guard",
        "override",
        "observation_redactor",
    }
)
"""The piighost sections a config may carry as stages."""

FORBIDDEN_SECTIONS = frozenset({"memory", "token_memo_ttl"})
"""Deployment-only sections a catalog config must not carry."""


def load_toml[T](path: Path, schema: type[T]) -> T:
    """Decode a TOML file into a schema, turning decode errors into ManifestError."""
    try:
        return msgspec.toml.decode(path.read_bytes(), type=schema)
    except FileNotFoundError as exc:
        raise ManifestError(f"{path}: file not found") from exc
    except msgspec.DecodeError as exc:
        raise ManifestError(f"{path}: {exc}") from exc
