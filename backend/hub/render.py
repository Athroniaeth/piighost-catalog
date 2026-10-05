"""Render resolved objects into piighost pipeline files.

The flattened form inlines every regex, so the file works offline and on any
piighost version that accepts the sections it carries. The referenced form keeps
``catalog:`` entries in ``catalogs`` for a piighost that resolves them itself. Memory
is never part of a shared config: it is appended on request from a preset.
"""

import json
import re
from typing import Any

from pydantic import ValidationError

from backend.hub.errors import ResolutionError
from backend.hub.refs import SCHEME
from backend.hub.resolve import ResolvedConfig, ResolvedLabels

MEMORY_PRESETS: dict[str, dict[str, Any]] = {
    "in_memory": {"type": "in_memory"},
    "redis": {
        "type": "redis",
        "url": "redis://localhost:6379/0",
        "namespace": "piighost",
        "hasher": {"type": "argon2"},
        "cipher": {"type": "aesgcm"},
    },
    "sqlalchemy": {
        "type": "sqlalchemy",
        "url_env": "PIIGHOST_DATABASE_URL",
        "hasher": {"type": "argon2"},
        "cipher": {"type": "aesgcm"},
    },
}


def render_pipeline(
    resolved: ResolvedConfig, *, keep_refs: bool = False, memory: str | None = None
) -> dict[str, Any]:
    """Return the piighost config of a resolved config, as a plain mapping."""
    detectors = _fold(
        [
            _render_detector(d.spec, d.labels, d.groups, keep_refs)
            for d in resolved.detectors
        ]
    )
    if not detectors:
        raise ResolutionError(f"{resolved.ref} has no detector left to render")
    data: dict[str, Any] = {"name": resolved.ref}
    data["detector"] = (
        detectors[0]
        if len(detectors) == 1
        else {
            "type": "composite",
            "detectors": detectors,
        }
    )
    data.update(resolved.stages)
    _append_memory(data, memory)
    return data


def render_labels_pipeline(
    labels: ResolvedLabels, *, keep_refs: bool = False, memory: str | None = None
) -> dict[str, Any]:
    """Return a regex-only pipeline for a group or a pattern."""
    data: dict[str, Any] = {
        "name": labels.ref,
        "detector": _render_detector(
            {"type": "regex"}, labels, [labels.ref], keep_refs
        ),
    }
    _append_memory(data, memory)
    return data


# What a detector carries, as opposed to how it is configured.
_CONTENT = ("patterns", "catalogs")


def _fold(detectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge neighbouring detectors that differ only by what they carry.

    A config names several regex detectors because that is how its sources are
    kept apart in the registry: one per group, so a child can exclude one by
    name and the composition check can replay them in order. None of that
    survives rendering — the flattened form keeps the type and the patterns and
    nothing else — so three ``[[detector.detectors]]`` blocks reading
    ``type = 'regex'`` were three ways of writing one.

    Merging is safe because a regex detector emits one detection per pattern in
    the order its mapping was built, and a composite concatenates its
    detectors' detections in order, so the concatenation of the three is the
    single mapping built in the same order. Verified over the registry: every
    config, every pattern example and every sample, identical spans and labels.

    Two limits keep that true. Only *neighbours* merge, because a detector of
    another kind between two regex ones is a step in the order. And a label
    carried twice with two different regexes blocks the merge, since one
    mapping cannot hold both and the second would silently win.
    """
    folded: list[dict[str, Any]] = []
    for detector in detectors:
        previous = folded[-1] if folded else None
        if previous is None or not _mergeable(previous, detector):
            folded.append(dict(detector))
            continue
        for key in _CONTENT:
            carried = detector.get(key)
            if carried is None:
                continue
            if isinstance(carried, dict):
                previous[key] = {**previous.get(key, {}), **carried}
            else:
                previous[key] = [*previous.get(key, []), *carried]
    return folded


def _mergeable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Same configuration, and no label claimed twice with two shapes."""
    if _settings(left) != _settings(right):
        return False
    here, there = left.get("patterns", {}), right.get("patterns", {})
    return all(here.get(label, regex) == regex for label, regex in there.items())


def _settings(detector: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in detector.items() if k not in _CONTENT}


def _render_detector(
    spec: dict[str, Any],
    labels: ResolvedLabels | None,
    groups: list[str],
    keep_refs: bool,
) -> dict[str, Any]:
    detector = dict(spec)
    if labels is None:
        return detector
    if keep_refs:
        detector["catalogs"] = [f"{SCHEME}{group}" for group in groups]
    else:
        detector["patterns"] = labels.regexes()
    return detector


def detector_only(data: dict[str, Any]) -> dict[str, Any]:
    """Keep the detector and drop what the config decided on your behalf.

    A config carries a linker, an anonymizer, sometimes a guard and a memory:
    choices about what happens once something has been found, which belong to
    the application and not to the registry. Someone who wants the registry's
    detection inside a pipeline they already have wants this half and none of
    the rest, and pasting it in is easier than deleting four sections.

    The result is a fragment, not a pipeline, so it is not offered to
    ``validate_pipeline`` — piighost would rightly refuse a config with no
    anonymizer.
    """
    return {"detector": data["detector"]}


def _append_memory(data: dict[str, Any], memory: str | None) -> None:
    if memory is None:
        return
    preset = MEMORY_PRESETS.get(memory)
    if preset is None:
        raise ResolutionError(
            f"unknown memory preset {memory!r}; choose among {sorted(MEMORY_PRESETS)}"
        )
    data["memory"] = json.loads(json.dumps(preset))


def validate_pipeline(data: dict[str, Any]) -> None:
    """Have the installed piighost validate a rendered pipeline, building nothing.

    Raises:
        ResolutionError: If piighost rejects the mapping.
    """
    from piighost.config import PipelineConfig

    try:
        PipelineConfig.model_validate(data)
    except ValidationError as exc:
        raise ResolutionError(f"piighost rejects the rendered pipeline: {exc}") from exc


# ------------------------------------------------------------------ TOML writer

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def to_toml(data: dict[str, Any]) -> str:
    """Serialize a pipeline mapping to TOML.

    Regexes are written as literal strings whenever possible, so backslashes
    stay single and the file reads like the pattern itself; a regex holding a
    quote falls back to a basic string with escapes.
    """
    lines: list[str] = []
    _emit_table(lines, [], data)
    return "\n".join(lines).rstrip("\n") + "\n"


def _emit_table(lines: list[str], path: list[str], table: dict[str, Any]) -> None:
    scalars = {
        k: v for k, v in table.items() if not _is_table(v) and not _is_table_array(v)
    }
    for key, value in scalars.items():
        lines.append(f"{_key(key)} = {_value(value)}")
    for key, value in table.items():
        if _is_table(value):
            # A table holding only sub-tables needs no header of its own: TOML
            # creates it implicitly when [a.b] appears.
            has_scalars = any(
                not _is_table(v) and not _is_table_array(v) for v in value.values()
            )
            if has_scalars or not value:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"[{'.'.join(_key(p) for p in [*path, key])}]")
            _emit_table(lines, [*path, key], value)
        elif _is_table_array(value):
            for item in value:
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"[[{'.'.join(_key(p) for p in [*path, key])}]]")
                _emit_table(lines, [*path, key], item)


def _is_table(value: Any) -> bool:
    return isinstance(value, dict)


def _is_table_array(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(v, dict) for v in value)
    )


def _key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else json.dumps(key, ensure_ascii=False)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        if "'" not in value and not any(ord(c) < 0x20 for c in value):
            return f"'{value}'"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    if value is None:
        raise ResolutionError("TOML has no null; drop the key instead")
    raise ResolutionError(f"cannot render {type(value).__name__} to TOML")
