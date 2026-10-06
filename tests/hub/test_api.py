import tomllib

from litestar import Litestar
from litestar.testing import AsyncTestClient

from backend.hub.registry import Registry
from backend.hub.routes import IMMUTABLE, REVALIDATE


class TestListing:
    async def test_vocabulary(self, client: AsyncTestClient[Litestar]) -> None:
        response = await client.get("/api/v1/vocabulary")
        assert response.status_code == 200
        tags = {item["tag"]: item["kind"] for item in response.json()["items"]}
        assert tags["fr"] == "region"

    async def test_list_and_filters(self, client: AsyncTestClient[Litestar]) -> None:
        everything = (await client.get("/api/v1/refs")).json()["items"]
        assert len(everything) == 7
        groups = (await client.get("/api/v1/refs", params={"kind": "group"})).json()[
            "items"
        ]
        assert sorted(g["name"] for g in groups) == ["all", "fr"]
        finance = (await client.get("/api/v1/refs", params={"tag": "finance"})).json()[
            "items"
        ]
        assert sorted(p["name"] for p in finance) == ["credit-card", "fr-siret"]
        assert everything[0]["pointers"]["latest"] == everything[0]["latest"]

    async def test_manifest_serves_the_source_file(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """The literal segment has to win over the commit selector beside it."""
        response = await client.get("/api/v1/refs/piighost/base/manifest")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "config"
        assert body["path"] == "configs/piighost/base/config.toml"
        assert 'name = "base"' in body["text"]
        assert 'type = "gliner2"' in body["text"]
        selector = await client.get("/api/v1/refs/piighost/base/latest")
        assert selector.status_code == 200

    async def test_manifest_of_an_unknown_object_is_404(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.get("/api/v1/refs/piighost/nope/manifest")
        assert response.status_code == 404

    async def test_object_detail_lists_commits(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.get("/api/v1/refs/piighost/all")
        assert response.status_code == 200
        body = response.json()
        assert body["kind"] == "group"
        assert [c["commit"] for c in body["commits"]] == [body["latest"]]
        assert body["commits"][0]["recorded_at"] is None

    async def test_object_detail_carries_its_title(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """What the page heading reads, and None where a manifest has none."""
        siret = (await client.get("/api/v1/refs/piighost/fr-siret")).json()
        assert siret["title"] == {"en": "SIRET (France)", "fr": "SIRET (France)"}
        group = (await client.get("/api/v1/refs/piighost/all")).json()
        assert group["title"] is None

    async def test_unknown_object_is_404(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.get("/api/v1/refs/piighost/nope")
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")


class TestCommits:
    async def test_commit_by_tag_and_by_hash_with_cache_headers(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        by_tag = await client.get("/api/v1/refs/piighost/all/latest")
        assert by_tag.status_code == 200
        assert by_tag.headers["cache-control"] == REVALIDATE
        short = by_tag.json()["commit"]
        by_hash = await client.get(f"/api/v1/refs/piighost/all/{short}")
        assert by_hash.status_code == 200
        assert by_hash.headers["cache-control"] == IMMUTABLE
        assert by_hash.headers["etag"] == f'"{by_tag.json()["digest"]}"'
        assert by_hash.json()["content"]["sources"][0]["ref"] == "piighost/fr"

    async def test_unknown_tag_is_404_and_bad_selector_is_400(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        assert (await client.get("/api/v1/refs/piighost/all/prod")).status_code == 404
        assert (await client.get("/api/v1/refs/piighost/all/Prod")).status_code == 400

    async def test_resolved_group_and_config(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        group = (await client.get("/api/v1/refs/piighost/all/latest/resolved")).json()
        assert [entry["label"] for entry in group["labels"]] == [
            "FR_SIRET",
            "EMAIL",
            "CREDIT_CARD",
        ]
        assert group["pipeline"]["detector"]["type"] == "regex"
        config = (
            await client.get("/api/v1/refs/piighost/child/latest/resolved")
        ).json()
        assert config["labels"] is None
        assert [d["name"] for d in config["detectors"]] == ["regex-all"]
        assert config["pipeline"]["expander"] == {"type": "word_boundary"}

    async def test_pipeline_toml(self, client: AsyncTestClient[Litestar]) -> None:
        response = await client.get(
            "/api/v1/refs/piighost/child/latest/pipeline.toml",
            params={"memory": "redis"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/toml")
        data = tomllib.loads(response.text)
        assert data["memory"]["type"] == "redis"
        assert list(data["detector"]["patterns"]) == ["FR_SIRET", "EMAIL"]
        refs = await client.get(
            "/api/v1/refs/piighost/child/latest/pipeline.toml",
            params={"keep_refs": "true"},
        )
        assert tomllib.loads(refs.text)["detector"]["catalogs"][0].startswith(
            "catalog:piighost/all:"
        )

    async def test_the_detector_can_be_taken_without_the_stages(
        self, client: AsyncTestClient[Litestar], registry: Registry
    ) -> None:
        """What a config decides after detection belongs to the application."""
        response = await client.get(
            "/api/v1/refs/piighost/child/latest/pipeline.toml",
            params={"part": "detector", "memory": "redis"},
        )
        assert response.status_code == 200
        ref = registry.heads["piighost/child"].ref
        assert response.text.startswith(f"# {ref}\n")
        data = tomllib.loads(response.text)
        # The ref rides in a comment: a fragment pasted into someone else's
        # config must not bring a name that overwrites theirs.
        assert set(data) == {"detector"}
        assert list(data["detector"]["patterns"]) == ["FR_SIRET", "EMAIL"]


class TestStats:
    async def test_stats_answers_before_anything_is_counted(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """A fresh deployment has no file yet, and the dashboard still draws."""
        response = await client.get("/api/v1/stats", params={"days": 7})
        assert response.status_code == 200
        body = response.json()
        assert body["pulls"] == 0
        assert len(body["per_day"]) == 7

    async def test_the_window_is_clamped_rather_than_refused(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        for days, expected in ((0, 1), (9999, 365)):
            response = await client.get("/api/v1/stats", params={"days": days})
            assert response.json()["days"] == expected

    async def test_a_pull_is_counted_and_a_health_check_is_not(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """End to end: through the hook, into the file, back out of the report.

        Measured as a delta. The client is session-scoped, so other tests have
        already pulled things, and an absolute count would be an assertion about
        the order the suite happens to run in.
        """
        from backend.app import USAGE_KEY

        usage = client.app.state[USAGE_KEY]
        await usage.flush()
        before = (await client.get("/api/v1/stats", params={"days": 1})).json()

        await client.get(
            "/api/v1/refs/piighost/child/latest/pipeline.toml",
            headers={"user-agent": "piighost-hub/1.7.2"},
        )
        await client.get("/api/health")
        await usage.flush()
        after = (await client.get("/api/v1/stats", params={"days": 1})).json()

        def count(body: dict, field: str, key: str) -> int:
            return next((row["count"] for row in body[field] if row["key"] == key), 0)

        assert after["pulls"] - before["pulls"] == 1
        assert (
            count(after, "top_objects", "piighost/child")
            - count(before, "top_objects", "piighost/child")
            == 1
        )
        assert (
            count(after, "clients", "piighost") - count(before, "clients", "piighost")
            == 1
        )
        # The health check touched nothing: only stats calls are browses, and
        # those are not counted either.
        assert after["browses"] == before["browses"]

    async def test_pull_counts_reach_the_catalogue_and_the_detail_page(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """The number is only useful where a configuration is chosen."""
        from backend.app import USAGE_KEY

        # Twenty, which is more than any other test in the suite pulls, so the
        # ranking holds whatever order the session-scoped client ran them in.
        usage = client.app.state[USAGE_KEY]
        for _ in range(20):
            await client.get(
                "/api/v1/refs/piighost/email/latest/pipeline.toml",
                headers={"user-agent": "piighost-hub/1.7.2"},
            )
        await usage.flush()

        detail = (await client.get("/api/v1/refs/piighost/email")).json()
        assert detail["pulls"] == 20

        ranked = (await client.get("/api/v1/search", params={"sort": "pulls"})).json()
        assert ranked["items"][0]["key"] == "piighost/email"
        assert ranked["items"][0]["pulls"] == 20
