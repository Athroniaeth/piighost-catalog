"""Reference grammar: ``[catalog:]namespace/name[:selector]``.

A selector is either a commit, exactly eight lowercase hex characters, or a tag.
That syntactic split is what lets one separator serve both: a tag made only of
hex characters is refused at publication, so the two sets never meet. ``latest``
is a tag every object carries, computed and never set by hand; a reference with
no selector means ``latest``. The scheme is optional, and the older ``hub:``
is still read, as the piighost library does.
"""

import re
from dataclasses import dataclass, replace

from backend.hub.errors import RefError

SCHEME = "catalog:"
LEGACY_SCHEME = "hub:"
LATEST = "latest"

_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMIT = re.compile(r"^[0-9a-f]{8}$")
_HEX_ONLY = re.compile(r"^[0-9a-f]+$")


def is_valid_name(text: str) -> bool:
    """Return whether text is a valid namespace or object name (kebab-case)."""
    return _NAME.fullmatch(text) is not None


def is_commit(selector: str) -> bool:
    """Return whether a selector designates a commit rather than a tag."""
    return _COMMIT.fullmatch(selector) is not None


def is_valid_tag(tag: str) -> bool:
    """Return whether a tag may be set by an author.

    A tag is kebab-case, is not ``latest`` (computed), and is not made only of
    hex characters (it would be mistaken for a commit).
    """
    return (
        _NAME.fullmatch(tag) is not None
        and tag != LATEST
        and _HEX_ONLY.fullmatch(tag) is None
    )


@dataclass(frozen=True, slots=True)
class Ref:
    """A parsed reference to a catalog object at a tag or a commit."""

    namespace: str
    name: str
    selector: str = LATEST

    @property
    def key(self) -> str:
        """The object identity, ``namespace/name``, without selector."""
        return f"{self.namespace}/{self.name}"

    @property
    def is_commit(self) -> bool:
        """Whether the selector is a commit rather than a tag."""
        return is_commit(self.selector)

    def at(self, selector: str) -> Ref:
        """Return the same object at another selector."""
        return replace(self, selector=selector)

    def __str__(self) -> str:
        return f"{self.key}:{self.selector}"


def strip_scheme(text: str) -> str:
    """Drop a leading ``catalog:`` or ``hub:`` scheme, and the ``//`` after it."""
    for scheme in (SCHEME, LEGACY_SCHEME):
        if text.startswith(scheme):
            return text[len(scheme) :].removeprefix("//")
    return text


def parse_ref(text: str) -> Ref:
    """Parse ``[catalog:][//]namespace/name[:selector]`` into a Ref.

    Raises:
        RefError: If the text does not follow the grammar.
    """
    body = strip_scheme(text.strip())

    namespace, sep, rest = body.partition("/")
    if not sep or "/" in rest:
        raise RefError(f"reference {text!r} must be namespace/name[:selector]")

    name, _, selector = rest.partition(":")
    selector = selector or LATEST

    if not is_valid_name(namespace):
        raise RefError(f"reference {text!r}: invalid namespace {namespace!r}")
    if not is_valid_name(name):
        raise RefError(f"reference {text!r}: invalid name {name!r}")
    if not (is_commit(selector) or selector == LATEST or is_valid_tag(selector)):
        raise RefError(f"reference {text!r}: invalid selector {selector!r}")

    return Ref(namespace=namespace, name=name, selector=selector)
