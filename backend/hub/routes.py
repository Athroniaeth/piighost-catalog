"""Read-only catalog API: what the piighost library and the site consume.

Public on purpose: a third party resolves ``catalog:`` references from its own
deployment, so these routes carry no API key guard. They only serve what the
registry already publishes. A commit is immutable, so a response selected by
commit is cached forever; one selected by tag must be revalidated.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

import msgspec
from litestar import Controller, Litestar, Request, Response, get
from litestar.datastructures import State
from litestar.params import FromPath, QueryParameter
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_422_UNPROCESSABLE_ENTITY

from backend import REGISTRY_ROOT
from backend.exceptions import AppError, NotFoundError
from backend.hub.errors import RefError, ResolutionError
from backend.hub.evaluate import diff_commits
from backend.hub.refs import Ref, is_commit, parse_ref
from backend.hub.registry import REGISTRY_DIR_ENV_VAR, Registry
from backend.hub.render import (
    detector_only,
    render_labels_pipeline,
    render_pipeline,
    to_toml,
)
from backend.hub.resolve import resolve_config, resolve_labels
from backend.hub.samples import Sample
from backend.hub.search import Index
from backend.hub.snippets import snippets
from backend.hub.store import Snapshot
from backend.hub.usage import database_path, pulls_by_object, report

STATE_KEY = "hub_registry"
INDEX_KEY = "hub_index"

IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "public, no-cache"
TOML_MEDIA_TYPE = "application/toml"

#: The window a pull count is shown over, everywhere it is shown.
PULL_WINDOW_DAYS = 30


class BadRequestError(AppError):
    status_code = HTTP_400_BAD_REQUEST
    detail = "Bad request"


class UnprocessableError(AppError):
    status_code = HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Unprocessable"


# ---------------------------------------------------------------- responses


class Localized(msgspec.Struct):
    en: str
    fr: str | None = None


class ObjectSummary(msgspec.Struct):
    key: str
    kind: Literal["pattern", "group", "config"]
    namespace: str
    name: str
    description: Localized
    tags: list[str]
    latest: str
    pointers: dict[str, str]


class ObjectList(msgspec.Struct):
    items: list[ObjectSummary]


class CommitSummary(msgspec.Struct):
    commit: str
    digest: str
    recorded_at: str | None


class ObjectDetail(msgspec.Struct):
    key: str
    kind: Literal["pattern", "group", "config"]
    namespace: str
    name: str
    description: Localized
    tags: list[str]
    latest: str
    pointers: dict[str, str]
    commits: list[CommitSummary]
    pulls: int
    """Pipelines fetched over the last thirty days. Zero until someone pulls."""


class CountOut(msgspec.Struct):
    key: str
    count: int


class StatsOut(msgspec.Struct):
    """How the catalog is used, over a window, from counters rather than a log."""

    days: int
    pulls: int
    browses: int
    searches: int
    per_day: list[CountOut]
    top_objects: list[CountOut]
    selectors: list[CountOut]
    clients: list[CountOut]


class ManifestOut(msgspec.Struct):
    """One object's manifest as it sits in the registry, ready to be forked."""

    key: str
    kind: Literal["pattern", "group", "config"]
    path: str
    text: str


class CommitDetail(msgspec.Struct):
    key: str
    kind: Literal["pattern", "group", "config"]
    commit: str
    digest: str
    recorded_at: str | None
    content: dict[str, Any]


class ResolvedLabelOut(msgspec.Struct):
    label: str
    regex: str
    pattern: str
    via: list[str]


class ResolvedDetectorOut(msgspec.Struct):
    name: str
    type: str
    groups: list[str]
    labels: list[ResolvedLabelOut] | None


class Resolved(msgspec.Struct):
    ref: str
    kind: Literal["pattern", "group", "config"]
    labels: list[ResolvedLabelOut] | None
    detectors: list[ResolvedDetectorOut] | None
    stages: dict[str, Any] | None
    pipeline: dict[str, Any]


class VocabularyEntry(msgspec.Struct):
    tag: str
    kind: str
    label: Localized


class VocabularyOut(msgspec.Struct):
    items: list[VocabularyEntry]


class SearchHit(msgspec.Struct):
    key: str
    kind: str
    namespace: str
    name: str
    commit: str
    tags: list[str]
    labels: list[str]
    used_by: list[str]
    description: Localized
    updated_at: str | None
    commits: int
    pulls: int
    """Pipelines fetched over the last thirty days."""


class FacetOut(msgspec.Struct):
    tag: str
    kind: str
    count: int


class SearchOut(msgspec.Struct):
    items: list[SearchHit]
    facets: list[FacetOut]
    total: int


class LabelOut(msgspec.Struct):
    label: str
    patterns: list[str]


class LabelsOut(msgspec.Struct):
    items: list[LabelOut]


class AnnotationOut(msgspec.Struct):
    value: str
    label: str


class SampleOut(msgspec.Struct):
    name: str
    title: Localized
    tags: list[str]
    text: str
    annotations: list[AnnotationOut]


class SamplesOut(msgspec.Struct):
    items: list[SampleOut]


class ChangeOut(msgspec.Struct):
    text: str
    start: int
    end: int
    before: str | None
    after: str | None
    sample: str


class DiffOut(msgspec.Struct):
    before: str
    after: str
    labels_added: list[str]
    labels_removed: list[str]
    changes: list[ChangeOut]
    behavioural: bool


class SnippetsOut(msgspec.Struct):
    ref: str
    items: dict[str, str]


class BadgeOut(msgspec.Struct):
    """The shields.io endpoint shape, so a README can show a live commit."""

    schemaVersion: int
    label: str
    message: str
    color: str


# ------------------------------------------------------------------ startup


def load_hub_registry(app: Litestar) -> None:
    """Load the registry once at startup; an invalid registry stops the app.

    Read from the environment here rather than at import so a test can point
    the app at a fixture tree before the lifespan runs.
    """
    root = os.getenv(REGISTRY_DIR_ENV_VAR)
    registry = Registry.load(REGISTRY_ROOT if root is None else Path(root))
    app.state[STATE_KEY] = registry
    # Built once: a registry is read far more often than it is published, and
    # nothing about it changes between two requests.
    app.state[INDEX_KEY] = Index(registry)


def registry_of(state: State) -> Registry:
    return state[STATE_KEY]


def index_of(state: State) -> Index:
    return state[INDEX_KEY]


# ---------------------------------------------------------------- controller


class HubController(Controller):
    """``/api/v1``: objects, commits, resolution and rendering."""

    path = "/v1"
    tags: Sequence[str] | None = ("catalog",)

    @get("/vocabulary", name="hub:vocabulary")
    async def vocabulary(self, state: State) -> VocabularyOut:
        registry = registry_of(state)
        return VocabularyOut(
            items=[
                VocabularyEntry(
                    tag=tag, kind=d.kind, label=Localized(d.label.en, d.label.fr)
                )
                for tag, d in registry.vocabulary.items()
            ]
        )

    @get("/refs", name="hub:list")
    async def list_objects(
        self,
        state: State,
        kind: Annotated[
            Literal["pattern", "group", "config"] | None,
            QueryParameter(description="Keep one kind only."),
        ] = None,
        tag: Annotated[
            str | None, QueryParameter(description="Keep objects carrying this tag.")
        ] = None,
    ) -> ObjectList:
        registry = registry_of(state)
        items = [
            _summary(registry, head)
            for key, head in sorted(registry.heads.items())
            if (kind is None or head.kind == kind)
            and (tag is None or tag in head.content.get("tags", []))
        ]
        return ObjectList(items=items)

    @get("/refs/{namespace:str}/{name:str}", name="hub:object")
    async def object_detail(
        self, state: State, namespace: FromPath[str], name: FromPath[str]
    ) -> ObjectDetail:
        registry = registry_of(state)
        ref = _ref(namespace, name)
        head = registry.heads.get(ref.key)
        if head is None:
            raise NotFoundError
        summary = _summary(registry, head)
        return ObjectDetail(
            **msgspec.structs.asdict(summary),
            pulls=pulls_by_object(database_path(), PULL_WINDOW_DAYS).get(ref.key, 0),
            commits=[
                CommitSummary(
                    commit=s.short, digest=s.digest, recorded_at=s.recorded_at
                )
                for s in registry.history(ref.key)
            ],
        )

    @get("/refs/{namespace:str}/{name:str}/manifest", name="hub:manifest")
    async def manifest(
        self, state: State, namespace: FromPath[str], name: FromPath[str]
    ) -> ManifestOut:
        """The head manifest verbatim, so a contributor starts from working TOML.

        The source file rather than a rendering of the frozen snapshot: what a
        contributor forks has to be the thing the maintainers read in review,
        comments and ordering included. Older commits are not served here, since
        they are stored as canonical JSON and forking one would hand back TOML
        nobody ever wrote.
        """
        registry = registry_of(state)
        obj = registry.objects.get(f"{namespace}/{name}")
        if obj is None:
            raise NotFoundError
        return ManifestOut(
            key=obj.key,
            kind=obj.kind,
            path=str(obj.path.relative_to(registry.root)),
            text=obj.path.read_text(encoding="utf-8"),
        )

    @get("/refs/{namespace:str}/{name:str}/{selector:str}", name="hub:commit")
    async def commit_detail(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        selector: FromPath[str],
    ) -> Response[CommitDetail]:
        snapshot = _snapshot(registry_of(state), _ref(namespace, name, selector))
        body = CommitDetail(
            key=snapshot.key,
            kind=snapshot.kind,
            commit=snapshot.short,
            digest=snapshot.digest,
            recorded_at=snapshot.recorded_at,
            content=snapshot.content,
        )
        return Response(body, headers=_cache_headers(selector, snapshot))

    @get(
        "/refs/{namespace:str}/{name:str}/{selector:str}/resolved", name="hub:resolved"
    )
    async def resolved(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        selector: FromPath[str],
    ) -> Response[Resolved]:
        registry = registry_of(state)
        snapshot = _snapshot(registry, _ref(namespace, name, selector))
        try:
            body = _resolve(registry, snapshot)
        except ResolutionError as exc:
            raise UnprocessableError(str(exc)) from exc
        return Response(body, headers=_cache_headers(selector, snapshot))

    @get(
        "/refs/{namespace:str}/{name:str}/{selector:str}/pipeline.toml",
        name="hub:pipeline",
    )
    async def pipeline_toml(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        selector: FromPath[str],
        memory: Annotated[
            Literal["in_memory", "redis", "sqlalchemy"] | None,
            QueryParameter(description="Append a memory section from this preset."),
        ] = None,
        keep_refs: Annotated[
            bool,
            QueryParameter(
                description="Keep catalog: references instead of inlining regexes."
            ),
        ] = False,
        part: Annotated[
            Literal["pipeline", "detector"],
            QueryParameter(
                description=(
                    "`detector` keeps the detector alone, without the stages "
                    "the config chose on your behalf."
                )
            ),
        ] = "pipeline",
    ) -> Response[str]:
        registry = registry_of(state)
        snapshot = _snapshot(registry, _ref(namespace, name, selector))
        try:
            if snapshot.kind == "config":
                data = render_pipeline(
                    resolve_config(registry, snapshot),
                    keep_refs=keep_refs,
                    memory=memory,
                )
            else:
                data = render_labels_pipeline(
                    resolve_labels(registry, snapshot),
                    keep_refs=keep_refs,
                    memory=memory,
                )
        except ResolutionError as exc:
            raise UnprocessableError(str(exc)) from exc
        if part == "detector":
            # The ref moves into a comment: a fragment pasted into someone
            # else's config must not bring a `name` that overwrites theirs,
            # and where it came from is worth keeping.
            body = f"# {snapshot.ref}\n{to_toml(detector_only(data))}"
        else:
            body = to_toml(data)
        return Response(
            body,
            media_type=TOML_MEDIA_TYPE,
            headers=_cache_headers(selector, snapshot),
        )

    @get("/search", name="hub:search")
    async def search(
        self,
        state: State,
        q: Annotated[
            str,
            QueryParameter(
                description="Free text over names, labels, tags and descriptions."
            ),
        ] = "",
        kind: Annotated[
            list[Literal["pattern", "group", "config"]] | None,
            QueryParameter(description="Repeatable. Kinds combine with OR."),
        ] = None,
        tag: Annotated[
            list[str] | None,
            QueryParameter(description="Repeatable. Tags combine with AND."),
        ] = None,
        label: Annotated[str | None, QueryParameter()] = None,
        sort: Annotated[
            Literal["relevance", "updated", "used", "labels", "pulls", "name"],
            QueryParameter(description="Order of the results."),
        ] = "relevance",
    ) -> SearchOut:
        """Search the registry and return the facet counts of the result set."""
        index = index_of(state)
        pulls = pulls_by_object(database_path(), PULL_WINDOW_DAYS)
        entries = index.search(
            q, kind=kind, tags=tag, label=label, sort=sort, pulls=pulls
        )
        return SearchOut(
            items=[
                SearchHit(
                    key=e.key,
                    kind=e.kind,
                    namespace=e.namespace,
                    name=e.name,
                    commit=e.commit,
                    tags=e.tags,
                    labels=e.labels,
                    used_by=e.used_by,
                    description=Localized(
                        en=e.description.get("en", ""), fr=e.description.get("fr", "")
                    ),
                    updated_at=e.updated_at,
                    commits=e.commits,
                    pulls=pulls.get(e.key, 0),
                )
                for e in entries
            ],
            facets=[
                FacetOut(tag=f.tag, kind=f.kind, count=f.count)
                for f in index.facets(entries)
            ],
            total=len(entries),
        )

    @get("/stats", name="hub:stats")
    async def stats(
        self,
        days: Annotated[
            int,
            QueryParameter(
                description="Window in days, 1 to 365.",
            ),
        ] = 30,
    ) -> Response[StatsOut]:
        """Public on purpose, like a package registry's download counts.

        There is nothing here to keep private: the finest resolution is the
        hour, the rows are shapes rather than requests, and no address, user
        agent or body is recorded anywhere. See `backend/hub/usage.py`.
        """
        window = max(1, min(days, 365))
        out = report(database_path(), days=window)
        body = StatsOut(
            days=out.days,
            pulls=out.pulls,
            browses=out.browses,
            searches=out.searches,
            per_day=[CountOut(key=r.key, count=r.count) for r in out.per_day],
            top_objects=[CountOut(key=r.key, count=r.count) for r in out.top_objects],
            selectors=[CountOut(key=r.key, count=r.count) for r in out.selectors],
            clients=[CountOut(key=r.key, count=r.count) for r in out.clients],
        )
        # A window of counters that only grows: a minute of staleness is fine
        # and it keeps a refreshed dashboard off the disk.
        return Response(body, headers={"Cache-Control": "public, max-age=60"})

    @get("/labels", name="hub:labels")
    async def labels(self, state: State) -> LabelsOut:
        """Every label the registry can emit, with the patterns that define it."""
        found = index_of(state).labels()
        return LabelsOut(
            items=[
                LabelOut(label=label, patterns=patterns)
                for label, patterns in found.items()
            ]
        )

    @get("/samples", name="hub:samples")
    async def samples(self, state: State) -> SamplesOut:
        """The annotated texts the playground offers and the scores are measured on."""
        return SamplesOut(
            items=[_sample_out(s) for s in registry_of(state).samples.values()]
        )

    @get(
        "/refs/{namespace:str}/{name:str}/{selector:str}/snippets", name="hub:snippets"
    )
    async def snippets_for(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        selector: FromPath[str],
    ) -> SnippetsOut:
        """Ready-to-paste ways to use this reference, one per target."""
        registry = registry_of(state)
        snapshot = _snapshot(registry, _ref(namespace, name, selector))
        return SnippetsOut(
            ref=snapshot.ref,
            items=snippets(
                snapshot.ref,
                snapshot.kind,
                regex_only=_is_regex_only(registry, snapshot),
                example=_example_text(registry, snapshot),
            ),
        )

    @get("/diff/{namespace:str}/{name:str}", name="hub:diff")
    async def diff(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        before: Annotated[str, QueryParameter(description="Older tag or commit.")],
        after: Annotated[
            str, QueryParameter(description="Newer tag or commit.")
        ] = "latest",
    ) -> DiffOut:
        """Compare two commits by what they detect on the corpus.

        A text diff of a regex says nothing actionable: one character can widen a
        pattern across half the corpus, or change nothing at all.
        """
        registry = registry_of(state)
        old = _snapshot(registry, _ref(namespace, name, before))
        new = _snapshot(registry, _ref(namespace, name, after))
        try:
            result = await diff_commits(
                registry, old, new, list(registry.samples.values())
            )
        except ResolutionError as exc:
            raise UnprocessableError(str(exc)) from exc
        return DiffOut(
            before=result.before,
            after=result.after,
            labels_added=result.labels_added,
            labels_removed=result.labels_removed,
            changes=[
                ChangeOut(
                    text=c.text,
                    start=c.start,
                    end=c.end,
                    before=c.before,
                    after=c.after,
                    sample=c.sample,
                )
                for c in result.changes
            ],
            behavioural=result.behavioural,
        )

    @get("/badge/{namespace:str}/{name:str}", name="hub:badge")
    async def badge(
        self,
        state: State,
        namespace: FromPath[str],
        name: FromPath[str],
        tag: Annotated[str, QueryParameter(description="Tag to report.")] = "latest",
    ) -> Response[BadgeOut]:
        """A shields.io endpoint, so a README can show the commit it pins."""
        snapshot = _snapshot(registry_of(state), _ref(namespace, name, tag))
        body = BadgeOut(
            schemaVersion=1,
            label=f"piighost catalog {tag}",
            message=f"{namespace}/{name}:{snapshot.short}",
            color="5865F2",
        )
        return Response(body, headers={"Cache-Control": REVALIDATE})


# ------------------------------------------------------------------ helpers


def _ref(namespace: str, name: str, selector: str | None = None) -> Ref:
    text = f"{namespace}/{name}" + (f":{selector}" if selector else "")
    try:
        return parse_ref(text)
    except RefError as exc:
        raise BadRequestError(str(exc)) from exc


def _snapshot(registry: Registry, ref: Ref) -> Snapshot:
    try:
        return registry.resolve(ref)
    except ResolutionError as exc:
        raise NotFoundError(str(exc)) from exc


def origin_of(request: Request) -> str:
    """The public origin, honouring the proxy headers nginx sets.

    Taken from the request rather than from configuration so a preview
    deployment, a local run and production each advertise themselves and not
    each other. Shared with robots.txt, the sitemap and llms.txt, which hand
    out URLs someone or something follows.
    """
    url = request.url
    scheme = request.headers.get("x-forwarded-proto", url.scheme)
    host = request.headers.get("host", url.netloc)
    return f"{scheme}://{host}"


def _is_regex_only(registry: Registry, snapshot: Snapshot) -> bool:
    """Whether the rendered detector is a plain regex one.

    Every pattern and every group is. A config usually is too, but three carry
    a model detector, and there the patterns are only half the pipeline: a
    snippet that pulled them out would quietly detect less than the object
    promises.
    """
    if snapshot.kind != "config":
        return True
    try:
        detector = render_pipeline(resolve_config(registry, snapshot))["detector"]
    except ResolutionError:
        return False
    blocks = detector["detectors"] if detector["type"] == "composite" else [detector]
    return all(block["type"] == "regex" for block in blocks)


def _example_text(registry: Registry, snapshot: Snapshot) -> str | None:
    """A sentence the object must catch, for its snippets to run on.

    A pattern's first "must match" example; for a group or a config, the first
    one of the first pattern it carries that has any. None when nothing does,
    or when the object does not resolve, and the snippet keeps its default.
    """
    try:
        if snapshot.kind == "config":
            patterns = [
                pattern
                for detector in resolve_config(registry, snapshot).regex_detectors()
                if detector.labels
                for pattern in detector.labels.patterns.values()
            ]
        else:
            patterns = list(resolve_labels(registry, snapshot).patterns.values())
    except ResolutionError:
        return None
    for pattern in patterns:
        matches = (pattern.content.get("examples") or {}).get("match") or []
        if matches:
            return str(matches[0]["text"])
    return None


def _cache_headers(selector: str, snapshot: Snapshot) -> dict[str, str]:
    return {
        "ETag": f'"{snapshot.digest}"',
        "Cache-Control": IMMUTABLE if is_commit(selector) else REVALIDATE,
    }


def _summary(registry: Registry, head: Snapshot) -> ObjectSummary:
    description = head.content["description"]
    return ObjectSummary(
        key=head.key,
        kind=head.kind,
        namespace=head.namespace,
        name=head.name,
        description=Localized(en=description["en"], fr=description["fr"]),
        tags=list(head.content.get("tags", [])),
        latest=head.short,
        pointers=registry.tags_of(head.key),
    )


def _resolve(registry: Registry, snapshot: Snapshot) -> Resolved:
    if snapshot.kind == "config":
        resolved = resolve_config(registry, snapshot)
        return Resolved(
            ref=resolved.ref,
            kind="config",
            labels=None,
            detectors=[
                ResolvedDetectorOut(
                    name=d.name,
                    type=str(d.spec.get("type")),
                    groups=list(d.groups),
                    labels=_labels_out(d.labels) if d.labels is not None else None,
                )
                for d in resolved.detectors
            ],
            stages=resolved.stages,
            pipeline=render_pipeline(resolved),
        )
    labels = resolve_labels(registry, snapshot)
    return Resolved(
        ref=labels.ref,
        kind=snapshot.kind,
        labels=_labels_out(labels),
        detectors=None,
        stages=None,
        pipeline=render_labels_pipeline(labels),
    )


def _sample_out(sample: Sample) -> SampleOut:
    return SampleOut(
        name=sample.name,
        title=Localized(en=sample.title.en, fr=sample.title.fr),
        tags=list(sample.tags),
        text=sample.text,
        annotations=[
            AnnotationOut(value=a.value, label=a.label) for a in sample.annotations
        ],
    )


def _labels_out(labels) -> list[ResolvedLabelOut]:
    return [
        ResolvedLabelOut(
            label=e.label, regex=e.regex, pattern=e.pattern, via=list(e.via)
        )
        for e in labels.labels.values()
    ]
