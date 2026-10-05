"""``python -m backend.hub``: check, record, resolve, render, log, tags.

Consuming a reference is the library's side: a ``catalog:`` entry in a pipeline
config, or ``RegexDetector.from_catalog`` and ``piighost.catalog.pull`` from
Python. These are the registry-side commands: what the CI runs and
what an author uses to see what a reference resolves to.
"""

import argparse
import json
import sys
from pathlib import Path

from backend import REGISTRY_ROOT
from backend.hub.checks import check_registry
from backend.hub.errors import HubError
from backend.hub.refs import parse_ref
from backend.hub.registry import Registry
from backend.hub.render import render_labels_pipeline, render_pipeline, to_toml
from backend.hub.resolve import resolve_config, resolve_labels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hub", description=__doc__)
    parser.add_argument(
        "--registry", type=Path, default=REGISTRY_ROOT, help="registry directory"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="validate manifests, run examples and bounds")
    check.add_argument(
        "--no-redos", action="store_true", help="skip the backtracking bound"
    )
    check.add_argument(
        "--allow-unrecorded",
        action="store_true",
        help="do not fail on unrecorded heads",
    )

    record = sub.add_parser("record", help="check, then record every unrecorded head")
    record.add_argument("--no-redos", action="store_true")

    resolve = sub.add_parser("resolve", help="print the flattened labels of a ref")
    resolve.add_argument("ref")
    resolve.add_argument("--json", action="store_true")

    render = sub.add_parser("render", help="print the piighost pipeline of a ref")
    render.add_argument("ref")
    render.add_argument("--keep-refs", action="store_true")
    render.add_argument("--memory", choices=["in_memory", "redis", "sqlalchemy"])
    render.add_argument("--json", action="store_true")

    log = sub.add_parser("log", help="list the commits of an object")
    log.add_argument("ref")

    tags = sub.add_parser("tags", help="list the tags of an object")
    tags.add_argument("ref")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except HubError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    registry = Registry.load(args.registry)

    if args.command in {"check", "record"}:
        recording = args.command == "record"
        report = check_registry(
            registry,
            redos=not args.no_redos,
            require_recorded=not (recording or args.allow_unrecorded),
        )
        for finding in report.findings:
            print(finding)
        if not report.ok:
            print(f"\n{len(report.errors)} error(s)", file=sys.stderr)
            return 1
        if recording:
            for key in sorted(registry.heads):
                head = registry.heads[key]
                if not registry.store.has(head):
                    registry.store.record(head)
                    print(f"recorded {head.ref}")
        print(f"\nOK: {len(registry.heads)} objects")
        return 0

    ref = parse_ref(args.ref)
    snapshot = registry.resolve(ref)

    if args.command == "resolve":
        if snapshot.kind == "config":
            resolved = resolve_config(registry, snapshot)
            payload = {
                "ref": resolved.ref,
                "detectors": [
                    {
                        "name": d.name,
                        "type": d.spec.get("type"),
                        "groups": d.groups,
                        "labels": [
                            {"label": e.label, "pattern": e.pattern, "via": list(e.via)}
                            for e in d.labels.labels.values()
                        ]
                        if d.labels
                        else None,
                    }
                    for d in resolved.detectors
                ],
                "stages": resolved.stages,
            }
        else:
            labels = resolve_labels(registry, snapshot)
            payload = {
                "ref": labels.ref,
                "labels": [
                    {
                        "label": e.label,
                        "regex": e.regex,
                        "pattern": e.pattern,
                        "via": list(e.via),
                    }
                    for e in labels.labels.values()
                ],
            }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            _print_resolved(payload)
        return 0

    if args.command == "render":
        if snapshot.kind == "config":
            data = render_pipeline(
                resolve_config(registry, snapshot),
                keep_refs=args.keep_refs,
                memory=args.memory,
            )
        else:
            data = render_labels_pipeline(
                resolve_labels(registry, snapshot),
                keep_refs=args.keep_refs,
                memory=args.memory,
            )
        print(
            json.dumps(data, indent=2, ensure_ascii=False)
            if args.json
            else to_toml(data),
            end="",
        )
        return 0

    if args.command == "log":
        for item in registry.history(ref.key):
            recorded = item.recorded_at or "unrecorded"
            print(f"{item.short}  {recorded}  {item.digest}")
        return 0

    for tag, short in sorted(registry.tags_of(ref.key).items()):
        print(f"{tag:12} {short}")
    return 0


def _print_resolved(payload: dict) -> None:
    print(payload["ref"])
    if "labels" in payload:
        for entry in payload["labels"]:
            via = " > ".join(entry["via"]) or "direct"
            print(f"  {entry['label']:22} {entry['pattern']:34} via {via}")
        return
    for detector in payload["detectors"]:
        print(f"  [{detector['type']}] {detector['name']}  groups={detector['groups']}")
        for entry in detector["labels"] or []:
            print(f"      {entry['label']:22} {entry['pattern']}")
    for section, stage in payload["stages"].items():
        print(f"  stage {section}: {stage}")
