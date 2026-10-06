"""robots.txt and sitemap.xml, the two files a crawler asks for by name."""

import json
from pathlib import Path
from xml.etree import ElementTree

from litestar import Litestar
from litestar.testing import AsyncTestClient

from backend.hub.registry import Registry
from backend.hub.seo import last_modified
from tests.hub.fixtures import write_pattern


class TestSeo:
    async def test_robots_points_at_the_sitemap(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.get("/robots.txt")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        body = response.text
        assert "Disallow: /api/" in body
        assert "Sitemap: http://testserver.local/sitemap.xml" in body

    async def test_sitemap_lists_every_object_and_the_static_pages(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.get("/sitemap.xml")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/xml")

        root = ElementTree.fromstring(response.text)
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        locations = [element.text or "" for element in root.iter(f"{namespace}loc")]

        for lang in ("en", "fr"):
            assert f"http://testserver.local/{lang}/" in locations
            assert f"http://testserver.local/{lang}/contribute" in locations
            assert f"http://testserver.local/{lang}/stats" in locations
            assert f"http://testserver.local/{lang}/r/piighost/base" in locations
        # The fixture registry holds seven objects, each with a page per language.
        assert sum(1 for loc in locations if "/r/" in loc) == 14
        # Nothing is listed outside a language: those paths only redirect.
        assert all(loc.split("/")[3] in ("en", "fr") for loc in locations)

    async def test_an_unrecorded_object_claims_no_date(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """No `lastmod` at all rather than today's date on every request."""
        response = await client.get("/sitemap.xml")
        assert "<lastmod>" not in response.text

    async def test_each_page_names_its_other_language(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """The sitemap carries the alternates the pages carry in their head."""
        root = ElementTree.fromstring((await client.get("/sitemap.xml")).text)
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        xhtml = "{http://www.w3.org/1999/xhtml}"
        page = next(
            url
            for url in root.iter(f"{namespace}url")
            if url.findtext(f"{namespace}loc")
            == "http://testserver.local/fr/r/piighost/base"
        )
        alternates = {
            link.get("hreflang"): link.get("href") for link in page.iter(f"{xhtml}link")
        }
        assert alternates == {
            "en": "http://testserver.local/en/r/piighost/base",
            "fr": "http://testserver.local/fr/r/piighost/base",
            "x-default": "http://testserver.local/en/r/piighost/base",
        }

    async def test_forwarded_proto_is_honoured(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """Behind nginx the request arrives over http; the site is https."""
        response = await client.get(
            "/sitemap.xml", headers={"x-forwarded-proto": "https"}
        )
        assert "https://testserver.local/en/" in response.text

    async def test_llms_points_at_the_pages_and_the_documentation(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """A page link names its language, and the docs are on their own host."""
        body = (await client.get("/llms.txt")).text
        assert "(http://testserver.local/en/r/piighost/base)" in body
        assert "https://docs.piighost.dev/en/" in body
        assert "athroniaeth.github.io" not in body

    async def test_llms_names_what_the_regexes_are_for(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """One sentence a search for "regex IBAN" can land on."""
        body = (await client.get("/llms.txt")).text
        line = next(line for line in body.splitlines() if line.startswith("Regex for"))
        assert all(word in line for word in ("SIRET", "IBAN", "NIR", "API keys"))


class TestLastModified:
    @staticmethod
    def record(root: Path, registry: Registry, key: str, when: str) -> None:
        """Write a commit file by hand, with a date that is not today."""
        head = registry.heads[key]
        path = registry.store.path_of(key, head.short)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"digest": head.digest, "recorded_at": when, "content": head.content}
        path.write_text(json.dumps(payload))

    def test_a_recorded_head_gives_the_day_it_was_recorded(
        self, root: Path, registry: Registry
    ) -> None:
        self.record(root, registry, "piighost/email", "2026-09-13T04:37:47+00:00")
        assert last_modified(Registry.load(root), "piighost/email") == "2026-09-13"

    def test_an_unrecorded_head_gives_none(self, registry: Registry) -> None:
        assert last_modified(registry, "piighost/email") is None
        assert last_modified(registry, "piighost/nope") is None

    def test_a_head_edited_since_its_last_commit_gives_none(
        self, root: Path, registry: Registry
    ) -> None:
        """The recorded date is the old content's, not the page's."""
        self.record(root, registry, "piighost/email", "2026-09-13T04:37:47+00:00")
        write_pattern(
            root,
            "email",
            "EMAIL",
            r"\b\w+@\w+\.com\b",
            matches=[("write to a@b.com now", "a@b.com")],
            no_matches=["a@b"],
        )
        assert last_modified(Registry.load(root), "piighost/email") is None
