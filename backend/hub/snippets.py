"""Ready-to-paste ways to use a reference, one per target."""

MIN_VERSION = "2.0"
"""The piighost release that ships RegexDetector.from_catalog and catalog: refs."""


def snippets(ref: str, kind: str, *, origin: str, regex_only: bool) -> dict[str, str]:
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
    """
    if not regex_only:
        return {"python": _whole_pipeline(ref, origin)}
    return {"python": _from_catalog(ref), "config": _catalog(ref)}


def _from_catalog(ref: str) -> str:
    """The detector by its id, which is what the registry is for."""
    return (
        f"# needs piighost >= {MIN_VERSION}\n"
        "from piighost.components.detector import RegexDetector\n\n"
        f'detector = RegexDetector.from_catalog("{ref}")\n'
        'found = await detector.detect("mail me at a@b.co")'
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


def _whole_pipeline(ref: str, origin: str) -> str:
    """A reference carrying a model detector is used whole, or not at all."""
    key, _, selector = ref.partition(":")
    url = f"{origin}/api/v1/refs/{key}/{selector}/pipeline.toml"
    return (
        "# This one carries a model detector as well as regexes, so it is\n"
        "# built whole rather than lifted apart.\n"
        "import tomllib\n"
        "import urllib.request\n\n"
        "from piighost.config import PipelineConfig\n\n"
        f'URL = "{url}"\n'
        "config = tomllib.loads(urllib.request.urlopen(URL).read().decode())\n\n"
        "pipeline = PipelineConfig.model_validate(config).build()\n"
        'result = await pipeline.anonymize("mail me at a@b.co")'
    )
