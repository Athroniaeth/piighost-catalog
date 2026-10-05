"""Ready-to-paste ways to use a reference, one per target."""

MIN_VERSION = "2.0"
"""The piighost release that ships RegexDetector.from_catalog, load_pipeline on a
catalog: reference, and catalog: refs in a pipeline file."""

FALLBACK_TEXT = "mail me at a@b.co"
"""The text a snippet runs when the object carries no example of its own."""


def snippets(
    ref: str,
    kind: str,
    *,
    regex_only: bool,
    example: str | None = None,
) -> dict[str, str]:
    """Ready-to-paste ways to use a reference: from Python, or from a config.

    The registry hands out regexes, so both recipes are about the detector.
    What a pipeline does afterwards — link, anonymize, remember — is the
    application's to choose, and a catalog that picked those for you would be a
    different kind of thing.

    ``regex_only`` says the rendered detector is a plain regex one, which is
    every pattern and group and all but three configs. Those three carry a
    model detector: their regexes are half the object, so they are shown being
    built whole and get no catalog recipe, since a catalogs entry cannot say
    model.

    ``example`` is a sentence the object must catch, the first of its "must
    match" examples, so the snippet of `jwt` runs on a token and not on an
    email address it would leave alone.
    """
    text = _python_string(example or FALLBACK_TEXT)
    if not regex_only:
        return {"python": _whole_pipeline(ref, text)}
    return {"python": _from_catalog(ref, text), "config": _catalog(ref)}


def _python_string(text: str) -> str:
    """A text as a Python literal on one line, quoted the way the snippets are."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _from_catalog(ref: str, text: str) -> str:
    """The detector by its id, which is what the catalog is for."""
    return (
        f"# needs piighost >= {MIN_VERSION}\n"
        "from piighost.components.detector import RegexDetector\n\n"
        f'detector = RegexDetector.from_catalog("{ref}")\n'
        f"found = await detector.detect({text})"
    )


def _catalog(ref: str) -> str:
    """The same reference named from a pipeline file, fetched when it builds."""
    return (
        "# pipeline.toml\n"
        "[detector]\n"
        "type = 'regex'\n"
        f"catalogs = ['catalog:{ref}']\n"
        "\n"
        "# Your own on top: an inline pattern wins on a shared label.\n"
        "[detector.patterns]\n"
        "INTERNAL_ID = 'EMP-\\d{6}'"
    )


def _whole_pipeline(ref: str, text: str) -> str:
    """A reference carrying a model detector is used whole, or not at all.

    ``load_pipeline`` pulls the whole configuration by its reference and builds
    it, caching a commit on disk as ``from_catalog`` does.
    """
    return (
        f"# needs piighost >= {MIN_VERSION}, with the extras its model needs.\n"
        "# This one carries a model detector as well as regexes, so it is\n"
        "# built whole rather than lifted apart.\n"
        "from piighost.config import load_pipeline\n\n"
        f'pipeline = load_pipeline("catalog:{ref}")\n'
        f"result = await pipeline.anonymize({text})"
    )
