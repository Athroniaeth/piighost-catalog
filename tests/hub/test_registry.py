from pathlib import Path

import pytest

from backend.hub.errors import ManifestError, ResolutionError
from backend.hub.refs import parse_ref
from backend.hub.registry import Registry
from tests.hub.fixtures import EMAIL, write, write_config, write_group, write_pattern


class TestEnglishOnly:
    def test_an_object_without_a_french_description_indexes(self, root: Path) -> None:
        """French is optional everywhere, `fr` may be missing.

        It was optional in the manifest model and required by the index, which
        joined both translations into the haystack and tripped over the None.
        """
        from backend.hub.search import Index

        write_pattern(
            root,
            "english-only",
            "ENGLISH_ONLY",
            r"\bEO-\d{4}\b",
            matches=[("code EO-1234 here", "EO-1234")],
            no_matches=["EO-12"],
            description='{ en = "An English-only description." }',
        )
        index = Index(Registry.load(root))
        assert index.entries["piighost/english-only"].description["fr"] == ""
        assert index.search("english-only")


class TestLoading:
    def test_heads_are_frozen_for_every_object(self, registry: Registry) -> None:
        assert set(registry.heads) == {
            "piighost/email",
            "piighost/credit-card",
            "piighost/fr-siret",
            "piighost/fr",
            "piighost/all",
            "piighost/base",
            "piighost/child",
        }
        assert registry.heads["piighost/fr"].kind == "group"
        assert len(registry.heads["piighost/fr"].short) == 8

    def test_every_structural_problem_is_reported_at_once(self, root: Path) -> None:
        write_pattern(root, "bad", "bad_label", "(", tags='["nope"]', no_matches=[])
        with pytest.raises(ManifestError) as info:
            Registry.load(root)
        message = str(info.value)
        assert "UPPER_SNAKE" in message
        assert "does not compile" in message
        assert "unknown tag 'nope'" in message
        assert "[[examples.no_match]]" in message

    def test_name_must_equal_directory(self, root: Path) -> None:
        path = write_pattern(root, "dir-name", "X", "x")
        path.write_text(path.read_text().replace('name = "dir-name"', 'name = "other"'))
        with pytest.raises(ManifestError, match="must equal its directory"):
            Registry.load(root)

    def test_unknown_key_is_rejected(self, root: Path) -> None:
        write_pattern(root, "typo", "TYPO", "typo", extra="regexx = 'x'")
        with pytest.raises(ManifestError, match="regexx"):
            Registry.load(root)

    def test_match_value_must_appear_exactly_once(self, root: Path) -> None:
        write_pattern(root, "twice", "TWICE", "ab", matches=[("ab and ab", "ab")])
        with pytest.raises(ManifestError, match="exactly once"):
            Registry.load(root)

    def test_regex_detector_refuses_inline_patterns(self, root: Path) -> None:
        write_config(
            root,
            "inline",
            """
[[detectors]]
name = "rx"
type = "regex"
groups = ["piighost/fr"]
patterns = { X = 'x' }
""",
        )
        with pytest.raises(ManifestError, match="inline patterns bypass"):
            Registry.load(root)

    def test_memory_is_a_deployment_concern(self, root: Path) -> None:
        write_config(
            root,
            "mem",
            """
[[detectors]]
name = "rx"
type = "regex"
groups = ["piighost/fr"]

[stages.memory]
type = "in_memory"
""",
        )
        with pytest.raises(ManifestError, match="deployment concern"):
            Registry.load(root)

    def test_exclude_entries_need_a_prefix(self, root: Path) -> None:
        write_config(
            root,
            "bad-exclude",
            '\n[[extends]]\nref = "piighost/base"\nexclude = ["ner"]\n',
        )
        with pytest.raises(ManifestError, match="must start with one of"):
            Registry.load(root)

    def test_exclude_and_only_are_exclusive(self, root: Path) -> None:
        write_group(
            root,
            "both",
            '\n[[sources]]\nref = "piighost/all"\nexclude = ["EMAIL"]\nonly = ["FR_SIRET"]\n',
        )
        with pytest.raises(ManifestError, match="exclusive"):
            Registry.load(root)

    @pytest.mark.parametrize("tag", ["latest", "deadbeef", "Prod"])
    def test_pointer_tags_follow_the_rules(self, root: Path, tag: str) -> None:
        write(root / "patterns/piighost/email/tags.toml", f'{tag} = "0123abcd"\n')
        with pytest.raises(ManifestError, match="not a valid tag"):
            Registry.load(root)


class TestFreezing:
    def test_reformatting_does_not_change_the_commit(self, root: Path) -> None:
        before = Registry.load(root).heads["piighost/email"].digest
        path = root / "patterns/piighost/email/pattern.toml"
        path.write_text("# a comment\n" + path.read_text().replace("\n\n", "\n\n\n"))
        assert Registry.load(root).heads["piighost/email"].digest == before

    def test_changing_a_pattern_changes_every_group_and_config_above_it(
        self, root: Path
    ) -> None:
        before = {k: v.digest for k, v in Registry.load(root).heads.items()}
        write_pattern(
            root,
            "email",
            "EMAIL",
            EMAIL + "x",
            matches=[("john.doe@example.comx", "john.doe@example.comx")],
        )
        after = {k: v.digest for k, v in Registry.load(root).heads.items()}
        changed = {k for k in before if before[k] != after[k]}
        assert changed == {
            "piighost/email",
            "piighost/all",
            "piighost/base",
            "piighost/child",
        }

    def test_cycle_is_refused(self, root: Path) -> None:
        write_group(root, "a", '\n[[sources]]\nref = "piighost/b"\n')
        write_group(root, "b", '\n[[sources]]\nref = "piighost/a"\n')
        with pytest.raises(ResolutionError, match="reference cycle"):
            Registry.load(root)

    def test_unknown_reference_is_refused(self, root: Path) -> None:
        write_group(root, "x", '\n[[sources]]\nref = "piighost/nope"\n')
        with pytest.raises(ResolutionError, match="unknown object"):
            Registry.load(root)


class TestResolvingReferences:
    def test_bare_and_latest_designate_the_head(self, registry: Registry) -> None:
        head = registry.heads["piighost/fr"]
        assert registry.resolve(parse_ref("piighost/fr")) is head
        assert registry.resolve(parse_ref("piighost/fr:latest")) is head
        assert registry.resolve(parse_ref(f"piighost/fr:{head.short}")) is head

    def test_a_tag_pins_a_recorded_commit_after_the_head_moved(
        self, root: Path
    ) -> None:
        registry = Registry.load(root)
        old = registry.heads["piighost/email"]
        registry.store.record(old)
        write(root / "patterns/piighost/email/tags.toml", f'prod = "{old.short}"\n')
        write_pattern(
            root,
            "email",
            "EMAIL",
            EMAIL + "x",
            matches=[("john.doe@example.comx", "john.doe@example.comx")],
        )
        registry = Registry.load(root)
        assert registry.heads["piighost/email"].short != old.short
        pinned = registry.resolve(parse_ref("piighost/email:prod"))
        assert pinned.digest == old.digest
        assert pinned.recorded_at is not None
        assert registry.tags_of("piighost/email") == {
            "prod": old.short,
            "latest": registry.heads["piighost/email"].short,
        }

    def test_a_group_pinned_by_tag_keeps_the_old_regex(self, root: Path) -> None:
        registry = Registry.load(root)
        old = registry.heads["piighost/email"]
        registry.store.record(old)
        write(root / "patterns/piighost/email/tags.toml", f'prod = "{old.short}"\n')
        write_group(root, "pinned", '\n[[sources]]\nref = "piighost/email:prod"\n')
        write_pattern(
            root,
            "email",
            "EMAIL",
            EMAIL + "x",
            matches=[("john.doe@example.comx", "john.doe@example.comx")],
        )
        registry = Registry.load(root)
        frozen = registry.heads["piighost/pinned"].content["sources"][0]
        assert frozen == {
            "ref": "piighost/email:prod",
            "commit": old.short,
            "exclude": [],
            "only": [],
        }

    def test_unknown_tag_and_commit(self, registry: Registry) -> None:
        with pytest.raises(ResolutionError, match="has no tag 'prod'"):
            registry.resolve(parse_ref("piighost/fr:prod"))
        with pytest.raises(ResolutionError, match="not a recorded commit"):
            registry.resolve(parse_ref("piighost/fr:00000000"))

    def test_history_lists_the_head_first_when_unrecorded(
        self, registry: Registry
    ) -> None:
        head = registry.heads["piighost/fr"]
        assert registry.history("piighost/fr") == [head]
        registry.store.record(head)
        assert [s.short for s in registry.history("piighost/fr")] == [head.short]


class TestMissingRegistry:
    def test_a_missing_directory_names_the_variable_to_set(
        self, tmp_path: Path
    ) -> None:
        """The failure an operator meets when the image ships no registry.

        The generic error would blame a missing vocabulary.toml, which sends them
        looking for a file rather than for the directory they forgot to mount.
        """
        with pytest.raises(ManifestError) as info:
            Registry.load(tmp_path / "absent")
        assert "HUB_REGISTRY_DIR" in str(info.value)
        assert "/app/registry" in str(info.value)
