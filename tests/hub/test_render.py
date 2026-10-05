import tomllib

import pytest

from backend.hub.errors import ResolutionError
from backend.hub.refs import parse_ref
from backend.hub.registry import Registry
from backend.hub.render import (
    _fold,
    render_labels_pipeline,
    render_pipeline,
    to_toml,
    validate_pipeline,
)
from backend.hub.resolve import resolve_config, resolve_labels


def config(registry: Registry, name: str):
    return resolve_config(registry, registry.resolve(parse_ref(f"piighost/{name}")))


class TestRender:
    def test_single_detector_is_not_wrapped_in_a_composite(
        self, registry: Registry
    ) -> None:
        data = render_pipeline(config(registry, "child"))
        assert data["detector"]["type"] == "regex"
        assert list(data["detector"]["patterns"]) == ["FR_SIRET", "EMAIL"]
        assert data["name"] == registry.heads["piighost/child"].ref
        validate_pipeline(data)

    def test_several_detectors_become_a_composite_in_order(
        self, registry: Registry
    ) -> None:
        data = render_pipeline(config(registry, "base"))
        assert data["detector"]["type"] == "composite"
        assert [d["type"] for d in data["detector"]["detectors"]] == [
            "regex",
            "gliner2",
        ]
        assert "name" not in data["detector"]["detectors"][1]
        validate_pipeline(data)

    def test_neighbouring_regex_detectors_fold_into_one(self) -> None:
        # Three blocks reading `type = 'regex'` and nothing else were three
        # ways of writing one. Order is what has to survive the fold, since
        # that is what decides an overlap.
        folded = _fold(
            [
                {"type": "regex", "patterns": {"FR_SIRET": "a"}},
                {"type": "regex", "patterns": {"EMAIL": "b", "URL": "c"}},
            ]
        )
        assert folded == [
            {"type": "regex", "patterns": {"FR_SIRET": "a", "EMAIL": "b", "URL": "c"}}
        ]

    def test_a_detector_of_another_kind_keeps_its_neighbours_apart(self) -> None:
        folded = _fold(
            [
                {"type": "regex", "patterns": {"EMAIL": "a"}},
                {"type": "gliner2", "labels": ["PERSON"]},
                {"type": "regex", "patterns": {"URL": "c"}},
            ]
        )
        assert [d["type"] for d in folded] == ["regex", "gliner2", "regex"]

    def test_a_label_carried_twice_with_two_shapes_blocks_the_fold(self) -> None:
        # One mapping cannot hold both, and the second would silently win.
        folded = _fold(
            [
                {"type": "regex", "patterns": {"EMAIL": "a"}},
                {"type": "regex", "patterns": {"EMAIL": "b"}},
            ]
        )
        assert [d["patterns"] for d in folded] == [{"EMAIL": "a"}, {"EMAIL": "b"}]

    def test_catalogs_fold_by_concatenation(self) -> None:
        folded = _fold(
            [
                {"type": "regex", "catalogs": ["catalog:piighost/fr"]},
                {"type": "regex", "catalogs": ["catalog:piighost/contact"]},
            ]
        )
        assert folded == [
            {
                "type": "regex",
                "catalogs": ["catalog:piighost/fr", "catalog:piighost/contact"],
            }
        ]

    def test_keep_refs_writes_catalog_references(self, registry: Registry) -> None:
        data = render_pipeline(config(registry, "child"), keep_refs=True)
        assert data["detector"]["catalogs"] == [
            f"catalog:{registry.heads['piighost/all'].ref}"
        ]
        assert "patterns" not in data["detector"]

    def test_memory_presets(self, registry: Registry) -> None:
        data = render_pipeline(config(registry, "child"), memory="redis")
        assert data["memory"]["hasher"] == {"type": "argon2"}
        validate_pipeline(data)
        with pytest.raises(ResolutionError, match="unknown memory preset"):
            render_pipeline(config(registry, "child"), memory="postgres")

    def test_a_group_renders_as_a_regex_only_pipeline(self, registry: Registry) -> None:
        labels = resolve_labels(registry, registry.resolve(parse_ref("piighost/all")))
        data = render_labels_pipeline(labels)
        assert data["detector"] == {"type": "regex", "patterns": labels.regexes()}
        validate_pipeline(data)

    def test_piighost_rejects_a_bad_stage(self, registry: Registry) -> None:
        data = render_pipeline(config(registry, "child"))
        data["linker"] = {"type": "nope"}
        with pytest.raises(ResolutionError, match="piighost rejects"):
            validate_pipeline(data)


class TestToml:
    def test_round_trips_through_tomllib(self, registry: Registry) -> None:
        data = render_pipeline(config(registry, "base"), memory="sqlalchemy")
        assert tomllib.loads(to_toml(data)) == data

    def test_regexes_are_literal_strings_unless_they_hold_a_quote(self) -> None:
        text = to_toml({"detector": {"patterns": {"A": r"\d+", "B": "it's"}}})
        assert r"A = '\d+'" in text
        assert 'B = "it\'s"' in text
        assert tomllib.loads(text)["detector"]["patterns"]["B"] == "it's"

    def test_arrays_of_tables_and_scalars(self) -> None:
        data = {
            "x": 1,
            "flag": True,
            "list": ["a", 2],
            "t": {"items": [{"a": 1}, {"a": 2, "sub": {"b": "c"}}]},
        }
        assert tomllib.loads(to_toml(data)) == data

    def test_null_is_refused(self) -> None:
        with pytest.raises(ResolutionError, match="no null"):
            to_toml({"a": None})
