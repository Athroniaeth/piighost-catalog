"""HTTP tests for the interactive routes and the read-only additions."""

from litestar import Litestar
from litestar.testing import AsyncTestClient

TEXT = "write to john.doe@example.com about SIRET 73282932000074"


class TestSearch:
    async def test_query_matches_name_label_and_description(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        body = (await client.get("/api/v1/search", params={"q": "siret"})).json()
        assert "piighost/fr-siret" in [i["key"] for i in body["items"]]
        assert body["total"] == len(body["items"])

    async def test_tags_combine_with_and(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        one = (await client.get("/api/v1/search", params={"tag": ["finance"]})).json()
        two = (
            await client.get("/api/v1/search", params={"tag": ["finance", "fr"]})
        ).json()
        assert two["total"] < one["total"]
        assert all({"finance", "fr"} <= set(i["tags"]) for i in two["items"])

    async def test_facets_count_the_result_set(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        body = (await client.get("/api/v1/search", params={"kind": "pattern"})).json()
        counts = {f["tag"]: f["count"] for f in body["facets"]}
        assert counts["contact"] == sum(
            1 for i in body["items"] if "contact" in i["tags"]
        )
        assert all(f["kind"] for f in body["facets"])

    async def test_filtering_by_label(self, client: AsyncTestClient[Litestar]) -> None:
        body = (await client.get("/api/v1/search", params={"label": "FR_SIRET"})).json()
        assert {i["key"] for i in body["items"]} >= {"piighost/fr-siret", "piighost/fr"}

    async def test_used_by_is_reported(self, client: AsyncTestClient[Litestar]) -> None:
        body = (await client.get("/api/v1/search", params={"q": "email"})).json()
        email = next(i for i in body["items"] if i["key"] == "piighost/email")
        assert email["used_by"] == ["piighost/all"]

    async def test_sort_orders(self, client: AsyncTestClient[Litestar]) -> None:
        by_name = (await client.get("/api/v1/search", params={"sort": "name"})).json()[
            "items"
        ]
        assert [i["name"] for i in by_name] == sorted(i["name"] for i in by_name)
        by_used = (await client.get("/api/v1/search", params={"sort": "used"})).json()[
            "items"
        ]
        counts = [len(i["used_by"]) for i in by_used]
        assert counts == sorted(counts, reverse=True)
        by_labels = (
            await client.get("/api/v1/search", params={"sort": "labels"})
        ).json()["items"]
        widths = [len(i["labels"]) for i in by_labels]
        assert widths == sorted(widths, reverse=True)
        assert (
            await client.get("/api/v1/search", params={"sort": "nope"})
        ).status_code == 400

    async def test_hits_carry_history_facts(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        item = (await client.get("/api/v1/search", params={"q": "email"})).json()[
            "items"
        ][0]
        # The fixture is unrecorded: one head, no date yet.
        assert item["commits"] == 1
        assert item["updated_at"] is None

    async def test_labels_and_samples(self, client: AsyncTestClient[Litestar]) -> None:
        labels = (await client.get("/api/v1/labels")).json()["items"]
        assert {"label": "EMAIL", "patterns": ["piighost/email"]} in labels
        samples = (await client.get("/api/v1/samples")).json()["items"]
        assert samples == []


class TestPlayground:
    async def test_run_returns_hits_and_rendered_text(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/playground", json={"ref": "piighost/all", "text": TEXT}
        )
        assert response.status_code == 200
        body = response.json()
        assert (
            body["anonymized_text"] == "write to <<EMAIL:1>> about SIRET <<FR_SIRET:1>>"
        )
        assert {h["label"] for h in body["hits"] if not h["kept"]} == {"CREDIT_CARD"}

    async def test_unknown_ref_is_404_and_bad_ref_is_400(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        assert (
            await client.post(
                "/api/v1/playground", json={"ref": "piighost/nope", "text": "x"}
            )
        ).status_code == 404
        assert (
            await client.post("/api/v1/playground", json={"ref": "Nope", "text": "x"})
        ).status_code == 400

    async def test_an_oversized_text_is_refused(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/playground", json={"ref": "piighost/all", "text": "a" * 50_000}
        )
        assert response.status_code == 400
        assert "playground accepts" in response.json()["detail"]

    async def test_candidate_regex_runs_and_catastrophic_one_is_refused(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        ok = await client.post(
            "/api/v1/playground/candidate",
            json={"regex": r"\bx\d{3}\b", "label": "CODE", "text": "see x123"},
        )
        assert ok.status_code == 200
        assert ok.json()["anonymized_text"] == "see <<CODE:1>>"
        bad = await client.post(
            "/api/v1/playground/candidate",
            json={"regex": r"(a+)+b", "text": "a" * 40 + "c"},
        )
        assert bad.status_code == 422
        assert "backtracks catastrophically" in bad.json()["detail"]

    async def test_chat_keeps_one_token_per_value(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/playground/chat",
            json={
                "ref": "piighost/all",
                "messages": ["mail john.doe@example.com", "again john.doe@example.com"],
            },
        )
        body = response.json()
        assert [t["user_sent"] for t in body["turns"]] == [
            "mail <<EMAIL:1>>",
            "again <<EMAIL:1>>",
        ]
        assert body["mapping"] == {"<<EMAIL:1>>": "john.doe@example.com"}
        assert "john.doe@example.com" in body["turns"][0]["reply_text"]

    async def test_chat_refuses_too_many_messages(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/playground/chat",
            json={"ref": "piighost/all", "messages": ["x"] * 30},
        )
        assert response.status_code == 400


class TestCompare:
    async def test_agreement_and_disagreement(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/compare",
            json={"refs": ["piighost/all", "piighost/fr"], "text": TEXT},
        )
        body = response.json()
        assert body["agreed"] == ["73282932000074"]
        assert body["disputed"] == ["john.doe@example.com"]
        assert [r["ref"].split(":")[0] for r in body["runs"]] == [
            "piighost/all",
            "piighost/fr",
        ]

    async def test_needs_at_least_two_references(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/compare", json={"refs": ["piighost/all"], "text": "x"}
        )
        assert response.status_code == 400


class TestSnippetsAndBadges:
    async def test_snippets_and_badge(self, client: AsyncTestClient[Litestar]) -> None:
        # base carries a model detector, so its patterns are only half the
        # pipeline and the snippet must build the whole thing.
        snippets = (
            await client.get("/api/v1/refs/piighost/base/latest/snippets")
        ).json()
        # No catalog recipe either: a catalogs entry cannot say model.
        assert set(snippets["items"]) == {"python"}
        assert "PipelineConfig" in snippets["items"]["python"]
        assert "RegexDetector" not in snippets["items"]["python"]
        badge = (await client.get("/api/v1/badge/piighost/all")).json()
        assert badge["schemaVersion"] == 1
        assert badge["message"].startswith("piighost/all:")

    async def test_a_group_is_used_through_its_detector(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """The registry hands out regexes, so both recipes are the detector."""
        body = (await client.get("/api/v1/refs/piighost/all/latest/snippets")).json()
        ref, items = body["ref"], body["items"]
        assert set(items) == {"python", "config"}
        assert f'RegexDetector.from_catalog("{ref}")' in items["python"]
        assert f"catalogs = ['catalog:{ref}']" in items["config"]

    async def test_no_snippet_names_a_command_that_does_not_exist(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """There is no piighost hub command, and no CLI or docker recipe left."""
        for key in ("piighost/all", "piighost/base", "piighost/child"):
            items = (await client.get(f"/api/v1/refs/{key}/latest/snippets")).json()[
                "items"
            ]
            assert set(items) <= {"python", "config"}, key
            for target, body in items.items():
                assert "piighost hub" not in body, (key, target)


class TestScoreAndDiff:
    async def test_diff_of_a_commit_against_itself_is_empty(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        head = (await client.get("/api/v1/refs/piighost/all")).json()["latest"]
        body = (
            await client.get(
                "/api/v1/diff/piighost/all", params={"before": head, "after": head}
            )
        ).json()
        assert body["behavioural"] is False


class TestSubmissions:
    MANIFEST = r"""
schema_version = 1

[pattern]
name = "order-id"
label = "ORDER_ID"
tags = ["contact"]
regex = '\bORD-[0-9]{6}\b'

[pattern.description]
en = "Order identifier."
fr = "Identifiant de commande."

[[examples.match]]
text = "order ORD-123456 shipped"
value = "ORD-123456"

[[examples.no_match]]
text = "ORD-12"
"""

    async def test_a_valid_submission_returns_a_pull_request_link(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/submissions/check",
            json={
                "kind": "pattern",
                "namespace": "alice",
                "name": "order-id",
                "manifest": self.MANIFEST,
            },
        )
        body = response.json()
        assert body["ok"], body["findings"]
        assert body["path"] == "patterns/alice/order-id/pattern.toml"
        assert body["pull_request_url"].startswith("https://github.com/")
        # The visitor is shown a registry path; GitHub is handed a repository
        # one, because the registry is a directory of this application.
        assert (
            "filename=registry%2Fpatterns%2Falice%2Forder-id"
            in body["pull_request_url"]
        )

    async def test_a_broken_submission_reports_findings_and_no_link(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        broken = self.MANIFEST.replace('text = "ORD-12"', 'text = "ORD-123456"')
        response = await client.post(
            "/api/v1/submissions/check",
            json={
                "kind": "pattern",
                "namespace": "alice",
                "name": "order-id",
                "manifest": broken,
            },
        )
        body = response.json()
        assert not body["ok"]
        assert body["pull_request_url"] is None
        assert any("must not be detected" in f["message"] for f in body["findings"])

    async def test_the_official_namespace_warns_without_refusing(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """It is the default in the form, because the maintainers publish too."""
        response = await client.post(
            "/api/v1/submissions/check",
            json={
                "kind": "pattern",
                "namespace": "piighost",
                "name": "order-id",
                "manifest": self.MANIFEST,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert [f["level"] for f in body["findings"]] == ["warning"]
        assert "maintainers" in body["findings"][0]["message"]


class TestPreview:
    """Flattening a group that is not in the registry yet."""

    async def test_merges_sources_in_order(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/groups/preview",
            json={"sources": [{"ref": "piighost/all"}]},
        )
        assert response.status_code == 200
        labels = [entry["label"] for entry in response.json()["labels"]]
        assert labels == ["FR_SIRET", "EMAIL", "CREDIT_CARD"]

    async def test_honours_an_exclusion(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/groups/preview",
            json={"sources": [{"ref": "piighost/all", "exclude": ["CREDIT_CARD"]}]},
        )
        labels = [entry["label"] for entry in response.json()["labels"]]
        assert "CREDIT_CARD" not in labels

    async def test_the_same_pattern_by_two_paths_is_a_diamond(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        """A draft gets the registry's rules, exception included.

        `all` already carries `email`, so naming it again is the same pattern
        commit reached twice. That is a diamond, and it is de-duplicated rather
        than refused; two *different* patterns emitting one label is what the
        registry calls an error.
        """
        response = await client.post(
            "/api/v1/groups/preview",
            json={"sources": [{"ref": "piighost/all"}, {"ref": "piighost/email"}]},
        )
        assert response.status_code == 200
        labels = [entry["label"] for entry in response.json()["labels"]]
        assert labels.count("EMAIL") == 1

    async def test_an_unknown_exclusion_is_an_error(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post(
            "/api/v1/groups/preview",
            json={"sources": [{"ref": "piighost/all", "exclude": ["NOPE"]}]},
        )
        assert response.status_code == 422

    async def test_no_sources_is_refused(
        self, client: AsyncTestClient[Litestar]
    ) -> None:
        response = await client.post("/api/v1/groups/preview", json={"sources": []})
        assert response.status_code == 400
