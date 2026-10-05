"""robots.txt, sitemap.xml and llms.txt, all generated from the registry.

Two things stand between a registry object and someone finding it: a crawler
has to be allowed in, and it has to be told the page exists. The site is a
single page application, so no link on it survives without JavaScript, which
makes the sitemap the only reliable way a search engine learns that
`/r/piighost/fr-default` is a page at all.

Both are generated rather than written by hand, for the same reason the site
is: the registry grows, and a list of 218 URLs maintained by a human is a list
of 180 URLs three weeks later. They sit at the site root rather than under
`/api`, because that is where a crawler looks, and nginx proxies the two exact
paths through.
"""

from __future__ import annotations

from datetime import UTC, datetime
from xml.sax.saxutils import escape

from litestar import Request, Response, get
from litestar.datastructures import State

from backend.hub.errors import ResolutionError
from backend.hub.registry import Registry
from backend.hub.resolve import resolve_config, resolve_labels
from backend.hub.routes import STATE_KEY, origin_of
from backend.hub.store import Snapshot

XML_MEDIA_TYPE = "application/xml"
TEXT_MEDIA_TYPE = "text/plain"

# The pages a crawler should know about that are not a registry object.
STATIC_PATHS = (
    "/",
    "/labels",
    "/configs",
    "/stats",
    "/playground",
    "/playground/compare",
    # /playground/chat is off, see CHAT_ENABLED in the frontend router. A
    # sitemap that advertises a route the app answers with its not-found page
    # is worse than a sitemap that omits it.
    "/contribute",
)

# An hour: the registry changes when a pull request lands, not by the minute.
CACHE = "public, max-age=3600"

_REPO = "https://github.com/Athroniaeth/piighost-hub"
"""Where the manifests live, which is the answer to "can I read the source"."""


@get(
    "/robots.txt",
    name="hub:robots",
    media_type=TEXT_MEDIA_TYPE,
    include_in_schema=False,
)
async def robots(request: Request) -> Response[str]:
    """Allow everything, and say where the sitemap is.

    The API is disallowed, not because it is secret, it is deliberately public,
    but because a crawler spending its budget on `/api/v1/refs/.../resolved`
    finds JSON where the same content already has an HTML page.
    """
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /schema\n"
        f"\nSitemap: {origin_of(request)}/sitemap.xml\n"
    )
    return Response(body, media_type=TEXT_MEDIA_TYPE, headers={"Cache-Control": CACHE})


@get(
    "/sitemap.xml",
    name="hub:sitemap",
    media_type=XML_MEDIA_TYPE,
    include_in_schema=False,
)
async def sitemap(request: Request, state: State) -> Response[str]:
    """Every static page, then one entry per registry object.

    A commit page is left out on purpose. It is immutable and there are several
    per object, so listing them would multiply the sitemap by the history depth
    to no benefit: the head page links to each of them.
    """
    registry: Registry = getattr(state, STATE_KEY)
    origin = origin_of(request)
    today = datetime.now(UTC).date().isoformat()

    entries = [f"<url><loc>{origin}{path}</loc></url>" for path in STATIC_PATHS]
    for key, head in sorted(registry.heads.items()):
        recorded = head.recorded_at[:10] if head.recorded_at else today
        entries.append(
            f"<url><loc>{origin}/r/{escape(key)}</loc>"
            f"<lastmod>{recorded}</lastmod></url>"
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    return Response(body, media_type=XML_MEDIA_TYPE, headers={"Cache-Control": CACHE})


@get(
    "/llms.txt",
    name="hub:llms",
    media_type=TEXT_MEDIA_TYPE,
    include_in_schema=False,
)
async def llms(request: Request, state: State) -> Response[str]:
    """What the registry is, for a model reading the site rather than a crawler.

    The llms.txt convention asks a site to say, in one file and in prose, what
    it holds and where. It matters more here than on most sites: the pages are
    rendered by JavaScript, and the assistants that answer "how do I redact PII
    before a prompt" read raw HTML. This file is the one place where the whole
    catalogue is legible without running anything.

    Generated, like the sitemap, because a hand-written list of 226 objects is a
    list of 180 three weeks later. Groups lead: a group is the set of regexes
    someone runs, and naming 147 patterns first would bury it.
    """
    registry: Registry = getattr(state, STATE_KEY)
    origin = origin_of(request)

    def section(kind: str, title: str, note: str) -> list[str]:
        rows = []
        for key, head in sorted(registry.heads.items()):
            if head.kind != kind:
                continue
            labels = _labels_of(registry, head)
            summary = _one_line(head.content.get("description", {}).get("en", ""))
            count = f" ({labels} labels)" if labels else ""
            rows.append(f"- [{key}]({origin}/r/{key}){count}: {summary}")
        if not rows:
            return []
        return [f"\n## {title}\n", note, ""] + rows

    lines = [
        "# piighost catalog",
        "",
        (
            "> A registry of tested de-identification regexes for piighost, a Python "
            "library that keeps personal data out of LLM prompts and puts it back in "
            "the response. Every pattern carries the cases it must catch, the cases it "
            "must leave alone, and a bound on its backtracking; every group is checked "
            "to still hold once its patterns are composed."
        ),
        "",
        (
            "An object is addressed by `namespace/name` and pinned by commit "
            "(`piighost/fr-default:7cc7cb30`) or by a movable tag. The identifier is "
            "the sha256 of the frozen manifest, so a pinned reference never changes "
            "under you."
        ),
        "",
        (
            "Use one from Python with "
            '`RegexDetector.from_catalog("piighost/logs")`, or name it in a pipeline '
            'file with `catalogs = ["catalog:piighost/logs"]`. '
            "Both need piighost 2.0 or later."
        ),
        "",
        "## How to read an object",
        "",
        f"- Its page: {origin}/r/NAMESPACE/NAME",
        (
            f"- Its detector, as TOML: {origin}/api/v1/refs/NAMESPACE/NAME/latest"
            "/pipeline.toml?part=detector"
        ),
        (
            f"- Its full pipeline: {origin}/api/v1/refs/NAMESPACE/NAME/latest"
            "/pipeline.toml"
        ),
        f"- Search the catalogue: {origin}/api/v1/search?q=QUERY",
    ]
    lines += section(
        "group",
        "Groups",
        "A group is a set of regexes checked to compose: each contributing "
        "pattern's examples are replayed against the whole group.",
    )
    lines += section(
        "pattern",
        "Patterns",
        "One shape and the label it emits.",
    )
    lines += section(
        "config",
        "piighost configurations",
        "A pipeline that carries regexes and decides what happens after "
        "detection. A different object from the regexes themselves.",
    )
    lines += [
        "",
        "## Elsewhere",
        "",
        "- [piighost, the library](https://github.com/Athroniaeth/piighost)",
        "- [piighost documentation](https://piighost.dev/)",
        f"- [This registry, on GitHub]({_REPO})",
        "",
    ]
    return Response(
        "\n".join(lines) + "\n",
        media_type=TEXT_MEDIA_TYPE,
        headers={"Cache-Control": CACHE},
    )


def _labels_of(registry: Registry, head: Snapshot) -> int:
    """How many labels an object covers, or zero when it carries none."""
    try:
        if head.kind == "config":
            resolved = resolve_config(registry, head)
            return sum(
                len(d.labels.labels) for d in resolved.regex_detectors() if d.labels
            )
        return len(resolve_labels(registry, head).labels)
    except ResolutionError:
        return 0


def _one_line(text: str) -> str:
    """The first sentence of a description, which is where its subject is."""
    first = text.strip().split(". ")[0].strip()
    if len(first) > 200:
        first = first[:197].rsplit(" ", 1)[0] + "…"
    return first + ("." if first and not first.endswith(".") else "")
