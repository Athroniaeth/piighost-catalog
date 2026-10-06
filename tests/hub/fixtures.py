"""Build small registries on disk for the hub tests.

Every helper writes one manifest; `make_registry` assembles the default fixture:
three patterns whose shapes collide on purpose (a 14-digit SIRET is also a
13-to-19-digit card number), two groups and two configs exercising exclusion,
inheritance and stages.
"""

from pathlib import Path

VOCABULARY = """
[fr]
kind = "region"
label = { en = "France", fr = "France" }
[international]
kind = "region"
label = { en = "International", fr = "International" }
[contact]
kind = "category"
label = { en = "Contact", fr = "Coordonnées" }
[finance]
kind = "category"
label = { en = "Finance", fr = "Financier" }
[chat]
kind = "use-case"
label = { en = "Chat", fr = "Chat" }
"""

EMAIL = r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}"
CARD = r"\b(?:\d[ -]?){12,18}\d\b"
SIRET = r"\b\d{3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{5}\b"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"))
    return path


def write_pattern(
    root: Path,
    name: str,
    label: str,
    regex: str,
    *,
    namespace: str = "piighost",
    tags: str = '["international"]',
    matches: list[tuple[str, str]] | None = None,
    no_matches: list[str] | None = None,
    extra: str = "",
    tail: str = "",
    description: str | None = None,
) -> Path:
    matches = (
        matches if matches is not None else [(f"value {label.lower()}", label.lower())]
    )
    no_matches = no_matches if no_matches is not None else ["nothing here"]
    # A table body, not a value: a caller passing `{ en = "..." }` gets an
    # English-only manifest, which is what the registry writes now.
    described = (
        description.strip("{} ")
        if description is not None
        else f'en = "{label} test pattern"\nfr = "Motif de test {label}"'
    )
    body = f"""
schema_version = 1

[pattern]
name = "{name}"
label = "{label}"
tags = {tags}
regex = '{regex}'
{extra}

[pattern.description]
{described}
"""
    for text, value in matches:
        body += f'\n[[examples.match]]\ntext = "{text}"\nvalue = "{value}"\n'
    for text in no_matches:
        body += f'\n[[examples.no_match]]\ntext = "{text}"\n'
    body += tail
    return write(root / "patterns" / namespace / name / "pattern.toml", body)


def write_group(
    root: Path,
    name: str,
    sources: str,
    *,
    namespace: str = "piighost",
    tags: str = '["contact"]',
) -> Path:
    body = f"""
schema_version = 1

[group]
name = "{name}"
description = {{ en = "{name}", fr = "{name}" }}
tags = {tags}
{sources}
"""
    return write(root / "groups" / namespace / name / "group.toml", body)


def write_config(
    root: Path, name: str, body: str, *, namespace: str = "piighost"
) -> Path:
    text = f"""
schema_version = 1

[config]
name = "{name}"
description = {{ en = "{name}", fr = "{name}" }}
tags = ["chat"]
piighost = ">=1.0"
{body}
"""
    return write(root / "configs" / namespace / name / "config.toml", text)


def make_registry(root: Path) -> Path:
    """The default fixture. See the module docstring."""
    write(root / "vocabulary.toml", VOCABULARY)
    write_pattern(
        root,
        "email",
        "EMAIL",
        EMAIL,
        tags='["international", "contact"]',
        matches=[("write to john.doe@example.com now", "john.doe@example.com")],
        no_matches=["john@doe", "not an email"],
    )
    write_pattern(
        root,
        "credit-card",
        "CREDIT_CARD",
        CARD,
        tags='["international", "finance"]',
        matches=[("card 4111 1111 1111 1111 ok", "4111 1111 1111 1111")],
        no_matches=["4111 1111"],
    )
    write_pattern(
        root,
        "fr-siret",
        "FR_SIRET",
        SIRET,
        tags='["fr", "finance"]',
        extra='title = { en = "SIRET (France)", fr = "SIRET (France)" }',
        matches=[("SIRET 73282932000074 ok", "73282932000074")],
        no_matches=["7328293200007"],
    )
    # fr first: on the identical 14-digit span FR_SIRET must win over CREDIT_CARD.
    write_group(
        root,
        "fr",
        """
[[sources]]
ref = "piighost/fr-siret"
""",
        tags='["fr"]',
    )
    write_group(
        root,
        "all",
        """
[[sources]]
ref = "piighost/fr"

[[sources]]
ref = "piighost/email"

[[sources]]
ref = "piighost/credit-card"
""",
    )
    write_config(
        root,
        "base",
        """
[[detectors]]
name = "regex-all"
type = "regex"
groups = ["piighost/all"]

[[detectors]]
name = "ner"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
labels = ["PERSON"]

[stages.linker]
type = "exact"

[stages.anonymizer.placeholder]
type = "label_counter"

[stages.guard]
type = "detector"

[stages.guard.detector]
type = "exact"
values = { Patrick = "PERSON" }
""",
    )
    write_config(
        root,
        "child",
        """
[[extends]]
ref = "piighost/base"
exclude = ["detector:ner", "label:CREDIT_CARD", "stage:guard"]

[stages.expander]
type = "word_boundary"
""",
    )
    return root
