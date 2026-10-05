"""Registry checks: what the CI of the registry runs, and what ``record`` requires.

Every check runs against the real piighost components, RegexDetector and
ConfidenceOverlapResolver, never against a re-implementation: a catalog that passed
its own tests but behaved differently in the library would be worse than none.

- Pattern examples: each ``match`` value is detected as itself, alone and wrapped
  in adjacent punctuation; each ``no_match`` text yields nothing.
- Composition: a group or a config replays the examples of every pattern it
  keeps, against the flattened set, through the resolver. A value stolen by a
  neighbour on the same span, or swallowed by a wider one, fails here.
- Backtracking bound: each regex scans an adversarial text of 100k characters in
  a subprocess with a time budget; a quadratic scan blows it, a hung one is killed.
- Store and tags: recorded snapshots still match their digest, every tag points
  at a known commit, and every head is recorded (unless told otherwise).
"""

import asyncio
import multiprocessing
import re
import time
from dataclasses import dataclass, field
from importlib.metadata import version as installed_version
from typing import Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version
from piighost.components.detector import RegexDetector
from piighost.components.overlap_resolver import ConfidenceOverlapResolver
from piighost.models import Detection

from backend.hub.errors import HubError
from backend.hub.registry import Registry
from backend.hub.render import render_pipeline, validate_pipeline
from backend.hub.resolve import ResolvedLabels, resolve_config, resolve_labels
from backend.hub.store import Snapshot

Level = Literal["error", "warning", "info"]

RESILIENCE_WRAPPERS: tuple[str, ...] = (
    "{v}.",
    "{v},",
    "{v}\n",
    " {v} ",
    "({v})",
    "Reach me at {v}.",
)
"""Adjacent punctuation a value must survive, detected alone and whole."""

REDOS_TEXT_LENGTH = 100_000
REDOS_BUDGET_SECONDS = 0.25
"""Per text. A linear scan of 100k characters lands two orders of magnitude
below; the margin absorbs a slow CI runner."""
REDOS_TIMEOUT_SECONDS = 5.0
"""Per pattern, all texts. Past it the subprocess is killed and the pattern fails."""
REDOS_DEFAULT_RECIPES: tuple[tuple[str, str, str], ...] = (
    ("", "1 ", "x"),
    ("", "1", "x"),
    ("", "a.", "@"),
    ("https://", ".", " "),
    ("", "A1", "!"),
    ("+33 6 ", "12 ", "x"),
    ("", "a", "!"),
    ("", "-", "x"),
)
"""Fillers tried when a pattern declares no ``[redos]`` recipe of its own."""


@dataclass(frozen=True, slots=True)
class Finding:
    level: Level
    subject: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():7} {self.subject}: {self.message}"


@dataclass(slots=True)
class Report:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: Level, subject: str, message: str) -> None:
        self.findings.append(Finding(level, subject, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_registry(
    registry: Registry, *, redos: bool = True, require_recorded: bool = True
) -> Report:
    """Run every check over a loaded registry and return the report."""
    report = Report()
    for problem in registry.store.verify():
        report.add("error", "commits", problem)

    patterns = [h for _, h in sorted(registry.heads.items()) if h.kind == "pattern"]
    if redos and patterns:
        check_backtracking(patterns, report)

    for key in sorted(registry.heads):
        head = registry.heads[key]
        try:
            if head.kind == "pattern":
                check_pattern(head, report)
            elif head.kind == "group":
                labels = resolve_labels(registry, head)
                check_composition(head.ref, [labels], report)
            else:
                check_config(registry, head, report)
        except HubError as exc:
            report.add("error", head.ref, str(exc))

        for tag, short in registry.tags_of(key).items():
            try:
                registry.snapshot(key, short)
            except HubError:
                report.add("error", f"{key}:{tag}", f"points at unknown commit {short}")

        if not registry.store.has(head):
            level: Level = "error" if require_recorded else "info"
            report.add(level, head.ref, "head is not recorded; run `hub record`")
    return report


# ------------------------------------------------------------------- patterns


def check_pattern(snapshot: Snapshot, report: Report) -> None:
    """Examples and resilience of one pattern; see check_backtracking for the bound."""
    content = snapshot.content
    label, regex = content["label"], content["regex"]
    single = ResolvedLabels(ref=snapshot.ref)
    single.labels[label] = _entry(snapshot)
    single.patterns[snapshot.ref] = snapshot
    check_composition(snapshot.ref, [single], report)

    if content.get("resilience", True):
        for example in content["examples"]["match"]:
            value = example["value"]
            for wrapper in RESILIENCE_WRAPPERS:
                kept = _detect([{label: regex}], wrapper.format(v=value))
                texts = [d.text for d in kept]
                if texts != [value]:
                    report.add(
                        "error",
                        snapshot.ref,
                        f"wrapped as {wrapper!r}, {value!r} is detected as {texts}, "
                        f"not alone and whole",
                    )


Recipe = tuple[str, str, str]
Job = tuple[str, str, list[Recipe]]
"""A backtracking job: the pattern ref, its regex, the recipes to scan."""


def backtracking_jobs(snapshots: list[Snapshot]) -> list[Job]:
    jobs: list[Job] = []
    for snapshot in snapshots:
        recipe = snapshot.content.get("redos")
        recipes: list[Recipe] = (
            [(recipe["prefix"], recipe["filler"], recipe["suffix"])]
            if recipe
            else list(REDOS_DEFAULT_RECIPES)
        )
        jobs.append((snapshot.ref, snapshot.content["regex"], recipes))
    return jobs


def check_backtracking(snapshots: list[Snapshot], report: Report) -> None:
    """Scan adversarial texts in a worker process; fail on a blown budget or a hang.

    One worker handles every pattern in turn and reports after each. When a
    pattern overruns its timeout the worker is killed, that pattern fails, and a
    fresh worker resumes with the rest: a hung regex costs one timeout, not the
    whole run.
    """
    jobs = backtracking_jobs(snapshots)
    results = measure_backtracking(jobs)
    for ref, regex, recipes in jobs:
        durations = results.get(ref)
        if durations is None:
            report.add(
                "error",
                ref,
                f"scan did not finish within {REDOS_TIMEOUT_SECONDS}s on an adversarial "
                f"text; catastrophic backtracking suspected",
            )
            continue
        for (prefix, filler, suffix), duration in zip(recipes, durations, strict=True):
            if duration > REDOS_BUDGET_SECONDS:
                report.add(
                    "error",
                    ref,
                    f"scan took {duration:.3f}s (budget {REDOS_BUDGET_SECONDS}s) on "
                    f"{prefix!r} + {filler!r}*N + {suffix!r}; the scan is not linear",
                )


def adversarial_text(prefix: str, filler: str, suffix: str) -> str:
    room = REDOS_TEXT_LENGTH - len(prefix) - len(suffix)
    return prefix + filler * max(room // max(len(filler), 1), 1) + suffix


def _worker(
    jobs: list[Job],
    text_length: int,
    queue: multiprocessing.Queue[tuple[str, list[float]]],
) -> None:
    """Scan each job's texts and report its durations; runs in the child."""
    for ref, regex, recipes in jobs:
        compiled = re.compile(regex, re.ASCII)
        durations: list[float] = []
        for prefix, filler, suffix in recipes:
            room = text_length - len(prefix) - len(suffix)
            text = prefix + filler * max(room // max(len(filler), 1), 1) + suffix
            started = time.perf_counter()
            compiled.findall(text)
            durations.append(time.perf_counter() - started)
        queue.put((ref, durations))


def measure_backtracking(jobs: list[Job]) -> dict[str, list[float] | None]:
    """Run the jobs in a spawned worker; None marks a job that overran its timeout."""
    context = multiprocessing.get_context("spawn")
    results: dict[str, list[float] | None] = {}
    pending = list(jobs)
    while pending:
        queue: multiprocessing.Queue[tuple[str, list[float]]] = context.Queue()
        process = context.Process(
            target=_worker, args=(pending, REDOS_TEXT_LENGTH, queue), daemon=True
        )
        process.start()
        while pending:
            ref = pending[0][0]
            try:
                done_ref, durations = queue.get(timeout=REDOS_TIMEOUT_SECONDS)
            except Exception:  # noqa: BLE001 - queue.Empty, or a dead worker
                results[ref] = None
                pending.pop(0)
                break
            results[done_ref] = durations
            pending.pop(0)
        process.kill()
        process.join()
    return results


# ---------------------------------------------------------------- composition


def check_composition(subject: str, sets: list[ResolvedLabels], report: Report) -> None:
    """Replay every contributing pattern's examples against the composed sets.

    ``sets`` are the regex detectors in pipeline order (one per group, or one per
    regex detector of a config); their detections are concatenated in that order
    and resolved, exactly as a composite detector would.
    """
    regex_sets = [labels.regexes() for labels in sets]
    kept_labels = {label for labels in sets for label in labels.labels}
    seen: set[str] = set()
    for labels in sets:
        for pattern_ref, snapshot in labels.patterns.items():
            if pattern_ref in seen:
                continue
            seen.add(pattern_ref)
            label = snapshot.content["label"]
            if label not in kept_labels:
                continue
            for example in snapshot.content["examples"]["match"]:
                kept = _detect(regex_sets, example["text"])
                if not any(
                    d.label == label and d.text == example["value"] for d in kept
                ):
                    start = example["text"].index(example["value"])
                    end = start + len(example["value"])
                    rivals = [
                        f"{d.label}={d.text!r}"
                        for d in kept
                        if d.span.start < end and d.span.end > start
                    ]
                    report.add(
                        "error",
                        subject,
                        f"{example['value']!r} from {pattern_ref} is not kept as {label}; "
                        f"covered by {rivals or 'nothing'}. Reorder the sources or exclude.",
                    )
            for example in snapshot.content["examples"]["no_match"]:
                kept = _detect(regex_sets, example["text"])
                stray = [d.text for d in kept if d.label == label]
                if stray:
                    report.add(
                        "error",
                        subject,
                        f"{example['text']!r} must not be detected as {label} "
                        f"({pattern_ref}), got {stray}",
                    )


def check_config(registry: Registry, head: Snapshot, report: Report) -> None:
    """Resolve, render and validate a config, then replay its regex examples."""
    resolved = resolve_config(registry, head)
    data = render_pipeline(resolved)
    validate_pipeline(data)
    _check_specifier(resolved.piighost, head.ref, report)
    sets = [d.labels for d in resolved.regex_detectors() if d.labels is not None]
    if sets:
        check_composition(head.ref, sets, report)


def _check_specifier(spec: str, subject: str, report: Report) -> None:
    if not spec:
        report.add("warning", subject, "no piighost version range declared")
        return
    try:
        specifier = SpecifierSet(spec)
    except InvalidSpecifier:
        report.add("error", subject, f"piighost = {spec!r} is not a version specifier")
        return
    current = Version(installed_version("piighost"))
    if not specifier.contains(current, prereleases=True):
        report.add(
            "error",
            subject,
            f"declares piighost {spec!r} but the checker runs {current}; the "
            f"validation above says nothing about the declared range",
        )


# -------------------------------------------------------------------- helpers


def _entry(snapshot: Snapshot):
    from backend.hub.resolve import ResolvedLabel

    return ResolvedLabel(
        label=snapshot.content["label"],
        regex=snapshot.content["regex"],
        pattern=snapshot.ref,
        via=(),
    )


def _detect(regex_sets: list[dict[str, str]], text: str) -> list[Detection]:
    """Concatenate the detectors' detections in order, then resolve overlaps."""

    async def run() -> list[Detection]:
        detections: list[Detection] = []
        for regexes in regex_sets:
            detections.extend(await RegexDetector(regexes).detect(text))
        return ConfidenceOverlapResolver().resolve(detections)

    return asyncio.run(run())
