"""The community path: check a manifest, then hand back a pull request."""

import urllib.parse

import pytest

from backend.hub.errors import HubError
from backend.hub.registry import Registry
from backend.hub.submissions import (
    check_submission,
    pull_request_url,
    repository_path,
    submission_path,
)
from tests.hub.fixtures import write_pattern

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

GROUP = """
schema_version = 1

[group]
name = "mine"
description = { en = "Mine", fr = "À moi" }
tags = ["contact"]

[[sources]]
ref = "piighost/email"

[[sources]]
ref = "piighost/credit-card"
"""


class TestChecking:
    async def test_a_valid_pattern_passes_and_gets_a_link(
        self, registry: Registry
    ) -> None:
        result = await check_submission(
            registry, "pattern", "alice", "order-id", MANIFEST
        )
        assert result.ok, result.findings
        assert result.path == "patterns/alice/order-id/pattern.toml"
        assert result.pull_request_url is not None

    async def test_a_group_resolves_against_the_real_neighbours(
        self, registry: Registry
    ) -> None:
        result = await check_submission(registry, "group", "alice", "mine", GROUP)
        assert result.ok, result.findings

    async def test_a_structural_error_names_the_visitor_path_not_a_temp_dir(
        self, registry: Registry
    ) -> None:
        result = await check_submission(
            registry,
            "pattern",
            "alice",
            "order-id",
            MANIFEST.replace("ORDER_ID", "bad label"),
        )
        assert not result.ok
        assert result.pull_request_url is None
        assert any("/tmp/" not in f.message for f in result.findings)
        assert all(
            "UPPER_SNAKE" in f.message or f.level != "error" for f in result.findings
        )

    async def test_composition_against_the_registry_is_checked(
        self, registry: Registry
    ) -> None:
        # Cards before SIRET: a fourteen-digit SIRET is also a card number of
        # shape, and on an identical span the first source declared wins. The
        # visitor learns that before opening a pull request, not in review.
        clashing = GROUP.replace(
            '[[sources]]\nref = "piighost/email"\n\n[[sources]]\nref = "piighost/credit-card"',
            '[[sources]]\nref = "piighost/credit-card"\n\n[[sources]]\nref = "piighost/fr-siret"',
        )
        result = await check_submission(registry, "group", "alice", "mine", clashing)
        assert not result.ok
        assert any("73282932000074" in f.message for f in result.findings)
        assert any("CREDIT_CARD" in f.message for f in result.findings)

    async def test_a_failing_example_is_reported(self, registry: Registry) -> None:
        result = await check_submission(
            registry,
            "pattern",
            "alice",
            "order-id",
            MANIFEST.replace('text = "ORD-12"', 'text = "ORD-123456"'),
        )
        assert not result.ok
        assert any("must not be detected" in f.message for f in result.findings)

    async def test_the_submission_never_touches_the_served_registry(
        self, registry: Registry, root
    ) -> None:
        before = sorted(p.name for p in (root / "patterns/piighost").iterdir())
        await check_submission(registry, "pattern", "alice", "order-id", MANIFEST)
        assert sorted(p.name for p in (root / "patterns/piighost").iterdir()) == before
        assert not (root / "patterns/alice").exists()


class TestRules:
    async def test_the_official_namespace_warns_without_refusing(
        self, registry: Registry
    ) -> None:
        """The maintainers submit here too, and this route authorises nothing."""
        result = await check_submission(
            registry, "pattern", "piighost", "order-id", MANIFEST
        )
        assert result.ok
        assert [f.level for f in result.findings] == ["warning"]
        assert "maintainers" in result.findings[0].message
        assert result.pull_request_url is not None

    async def test_an_existing_object_is_refused(
        self, registry: Registry, root
    ) -> None:
        write_pattern(root, "taken", "TAKEN", "taken", namespace="alice")
        reloaded = Registry.load(root)
        with pytest.raises(HubError, match="already exists"):
            await check_submission(reloaded, "pattern", "alice", "taken", MANIFEST)

    async def test_unknown_kind_and_bad_names(self, registry: Registry) -> None:
        with pytest.raises(HubError, match="unknown kind"):
            await check_submission(registry, "sample", "alice", "x", MANIFEST)
        with pytest.raises(HubError, match="kebab-case"):
            await check_submission(registry, "pattern", "Alice", "x", MANIFEST)


class TestPullRequest:
    def test_the_link_carries_the_path_and_the_manifest(self) -> None:
        path = submission_path("pattern", "alice", "order-id")
        url = pull_request_url(path, "body = 1", "owner/repo", "develop")
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        assert parsed.netloc == "github.com"
        assert parsed.path == "/owner/repo/new/develop"
        assert query["filename"] == [path]
        assert query["value"] == ["body = 1"]

    def test_paths_follow_the_registry_layout(self) -> None:
        assert submission_path("group", "a", "b") == "groups/a/b/group.toml"
        assert submission_path("config", "a", "b") == "configs/a/b/config.toml"

    def test_the_repository_path_carries_the_registry_directory(self) -> None:
        """GitHub wants a path from the repository root; the checks do not."""
        path = submission_path("pattern", "alice", "order-id")
        assert repository_path(path) == f"registry/{path}"


class TestDeployment:
    async def test_the_pull_request_target_comes_from_the_environment(
        self, registry: Registry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HUB_REGISTRY_REPO", "acme/our-registry")
        monkeypatch.setenv("HUB_REGISTRY_BRANCH", "main")
        result = await check_submission(
            registry, "pattern", "alice", "order-id", MANIFEST
        )
        assert result.pull_request_url is not None
        assert result.pull_request_url.startswith(
            "https://github.com/acme/our-registry/new/main?"
        )

    async def test_it_falls_back_to_the_official_registry(
        self, registry: Registry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("HUB_REGISTRY_REPO", raising=False)
        monkeypatch.delenv("HUB_REGISTRY_BRANCH", raising=False)
        result = await check_submission(
            registry, "pattern", "alice", "order-id", MANIFEST
        )
        assert result.pull_request_url is not None
        assert "/Athroniaeth/piighost-catalog/new/main?" in result.pull_request_url
        assert "filename=registry%2Fpatterns%2F" in result.pull_request_url
