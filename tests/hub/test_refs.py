import pytest

from backend.hub.errors import RefError
from backend.hub.refs import Ref, is_valid_tag, parse_ref


class TestParse:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("piighost/fr", Ref("piighost", "fr", "latest")),
            ("piighost/fr:prod", Ref("piighost", "fr", "prod")),
            ("piighost/fr:3fa9c2e1", Ref("piighost", "fr", "3fa9c2e1")),
            ("catalog:piighost/fr:prod", Ref("piighost", "fr", "prod")),
            ("catalog://piighost/fr", Ref("piighost", "fr", "latest")),
            # The scheme the library read before 2.0, still accepted.
            ("hub:piighost/fr:prod", Ref("piighost", "fr", "prod")),
            ("hub://piighost/fr", Ref("piighost", "fr", "latest")),
            (
                "  piighost/fr-notariat:latest ",
                Ref("piighost", "fr-notariat", "latest"),
            ),
        ],
    )
    def test_grammar(self, text: str, expected: Ref) -> None:
        assert parse_ref(text) == expected

    def test_eight_hex_characters_are_a_commit_anything_else_a_tag(self) -> None:
        assert parse_ref("a/b:3fa9c2e1").is_commit
        assert not parse_ref("a/b:prod").is_commit
        assert not parse_ref("a/b:prod-3fa9c2e1").is_commit
        # Seven hex characters would be a tag, and hex-only tags are refused, so
        # the two sets never meet.
        with pytest.raises(RefError):
            parse_ref("a/b:3fa9c2e")

    @pytest.mark.parametrize(
        "text",
        [
            "fr",
            "piighost/fr/extra",
            "Piighost/fr",
            "piighost/fr:Prod",
            "piighost/fr:3fa9c2e",
            "/fr",
            "piighost/:x",
        ],
    )
    def test_invalid(self, text: str) -> None:
        with pytest.raises(RefError):
            parse_ref(text)

    def test_key_and_str_and_at(self) -> None:
        ref = parse_ref("piighost/fr:prod")
        assert ref.key == "piighost/fr"
        assert str(ref) == "piighost/fr:prod"
        assert str(ref.at("deadbeef")) == "piighost/fr:deadbeef"


class TestTags:
    def test_valid_tags(self) -> None:
        assert is_valid_tag("prod")
        assert is_valid_tag("preprod-2")
        assert is_valid_tag("v1")

    def test_latest_and_hex_only_are_refused(self) -> None:
        assert not is_valid_tag("latest")
        assert not is_valid_tag("deadbeef")
        assert not is_valid_tag("abc")
        assert not is_valid_tag("Prod")
