"""Check a manifest a visitor wrote, and turn it into a pull request.

The registry is git-first, so publishing is a pull request, not a write
endpoint. That is not a limitation to work around: a config ships into other
people's pipelines, review is the trust boundary, and git already enforces
authorship, history and reverts. What the site adds is the part a contributor
cannot do alone, running the real checks before the pull request exists, so a
review argues about the pattern rather than about a missing example.
"""

import asyncio
import os
import shutil
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

import msgspec

from backend.hub.checks import check_pattern, check_registry
from backend.hub.errors import HubError, ManifestError
from backend.hub.refs import is_valid_name
from backend.hub.registry import KIND_DIRS, MANIFEST_FILES, Registry
from backend.hub.store import Kind

REPO_ENV_VAR = "HUB_REGISTRY_REPO"
BRANCH_ENV_VAR = "HUB_REGISTRY_BRANCH"
DEFAULT_REPO = "Athroniaeth/piighost-catalog"
"""Where a contribution lands: this application's repository.

The registry is a directory of it rather than a repository of its own, so
there is one source of truth and no sync step between the tree the checks run
against and the tree a visitor edits. REGISTRY_PREFIX is the cost of that
choice.
"""

DEFAULT_BRANCH = "main"
"""The branch a pull request targets."""

REGISTRY_PREFIX = "registry"
"""Where the registry tree sits inside the repository.

submission_path builds a path for GitHub's create-a-file link, which is
relative to the repository root, while the registry's own paths are relative
to the registry root.
"""


def configured_repo() -> tuple[str, str]:
    """The repository and branch a submission's pull request targets.

    Read from the environment on every call rather than at import, so a fork can
    point the contribution page at its own registry without rebuilding an image,
    and so a test can change it without reloading the module.
    """
    return (
        os.getenv(REPO_ENV_VAR) or DEFAULT_REPO,
        os.getenv(BRANCH_ENV_VAR) or DEFAULT_BRANCH,
    )


KINDS: tuple[Kind, ...] = ("pattern", "group", "config")


class Finding(msgspec.Struct):
    level: Literal["error", "warning", "info"]
    subject: str
    message: str


class SubmissionResult(msgspec.Struct):
    """What a visitor gets back: the verdict, the findings, and the next step."""

    ok: bool
    path: str
    findings: list[Finding]
    pull_request_url: str | None
    """A prefilled GitHub new-file link, or None while the manifest still fails."""


def submission_path(kind: Kind, namespace: str, name: str) -> str:
    """Where a submission of this kind lives in the registry tree."""
    return f"{KIND_DIRS[kind]}/{namespace}/{name}/{MANIFEST_FILES[kind]}"


def repository_path(path: str) -> str:
    """The same path seen from the repository root, which GitHub needs.

    Two paths, because they answer two questions: a registry path is what the
    checks stage and what the visitor is shown, and a repository path is where
    the file goes once the registry is a directory of the application. Using
    one for the other stages the manifest outside the tree it is checked in.
    """
    return f"{REGISTRY_PREFIX}/{path}"


def pull_request_url(path: str, manifest: str, repo: str, branch: str) -> str:
    """A GitHub "create new file" link, prefilled with the manifest.

    This is the whole community path: no OAuth application, no token held here,
    no write access to the registry from this service. The contributor is
    already signed in to GitHub, and the fork and the branch are GitHub's job.
    """
    query = urllib.parse.urlencode({"filename": path, "value": manifest})
    return f"https://github.com/{repo}/new/{branch}?{query}"


async def check_submission(
    registry: Registry,
    kind: str,
    namespace: str,
    name: str,
    manifest: str,
    *,
    repo: str | None = None,
    branch: str | None = None,
) -> SubmissionResult:
    """Check a submission off the event loop.

    The work is blocking twice over: it copies the registry to a temporary tree,
    and the checks drive the pipeline with asyncio.run, which cannot be called
    from inside a running loop. A worker thread gives both what they need.
    """
    configured = configured_repo()
    return await asyncio.to_thread(
        _check_submission,
        registry,
        kind,
        namespace,
        name,
        manifest,
        repo or configured[0],
        branch or configured[1],
    )


def _check_submission(
    registry: Registry,
    kind: str,
    namespace: str,
    name: str,
    manifest: str,
    repo: str,
    branch: str,
) -> SubmissionResult:
    """Validate a manifest as if it were already in the registry.

    The manifest is written into a copy of the registry so that its references
    resolve and the composition check sees the real neighbours. The copy is a
    temporary directory that never touches the served tree.

    Raises:
        HubError: If the submission's own coordinates are unusable.
    """
    if kind not in KINDS:
        raise HubError(f"unknown kind {kind!r}; expected one of {', '.join(KINDS)}")
    # Narrowed by the check above, which pyrefly cannot see through a plain `in`.
    checked_kind: Kind = kind  # type: ignore[assignment]
    if not is_valid_name(namespace) or not is_valid_name(name):
        raise HubError("namespace and name must be kebab-case")
    path = submission_path(checked_kind, namespace, name)
    if f"{namespace}/{name}" in registry.objects:
        raise HubError(
            f"{namespace}/{name} already exists; submit a new commit on it instead"
        )

    findings: list[Finding] = []
    # A note rather than a refusal. This route validates a manifest, it does not
    # authorise anything: the pull request it prepares lands in a repository
    # where a maintainer merges it or does not, so refusing the official
    # namespace here stopped nobody and blocked the maintainers themselves.
    if namespace == "piighost":
        findings.append(
            Finding(
                level="warning",
                subject=path,
                message=(
                    "the piighost namespace is the maintainers'; a submission here "
                    "needs one of them to merge it"
                ),
            )
        )

    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "registry"
        _copy_registry(registry.root, root)
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(manifest)
        try:
            candidate = Registry.load(root)
        except ManifestError as exc:
            findings += [
                Finding(level="error", subject=path, message=line)
                for line in str(exc).splitlines()
                if str(root) in line or line.strip()
            ]
            return SubmissionResult(
                ok=False,
                path=path,
                findings=_clean(findings, root),
                pull_request_url=None,
            )
        except HubError as exc:
            findings.append(Finding(level="error", subject=path, message=str(exc)))
            return SubmissionResult(
                ok=False,
                path=path,
                findings=_clean(findings, None),
                pull_request_url=None,
            )

        key = f"{namespace}/{name}"
        head = candidate.heads[key]
        report = check_registry(candidate, redos=False, require_recorded=False)
        if head.kind == "pattern":
            check_pattern(head, report)
        findings += [
            Finding(level=f.level, subject=f.subject, message=f.message)
            for f in report.findings
            if (
                f.subject == head.ref
                or f.subject in {key, path}
                or _touches(f.subject, candidate, key)
            )
            # "not recorded" is a maintainer step that happens after the pull
            # request is merged; showing it to a contributor asks them to run a
            # command they have no repository for.
            and "not recorded" not in f.message
        ]

    ok = not any(f.level == "error" for f in findings)
    return SubmissionResult(
        ok=ok,
        path=path,
        findings=_clean(findings, None),
        pull_request_url=(
            pull_request_url(repository_path(path), manifest, repo, branch)
            if ok
            else None
        ),
    )


def _touches(subject: str, registry: Registry, key: str) -> bool:
    """Whether a finding is about an object that references the submission."""
    subject_key = subject.split(":", 1)[0]
    head = registry.heads.get(subject_key)
    if head is None:
        return False
    from backend.hub.search import _referenced

    return key in _referenced(head)


def _clean(findings: list[Finding], root: Path | None) -> list[Finding]:
    """Strip the temporary path from messages, so a visitor sees their file."""
    if root is None:
        return findings
    prefix = str(root) + "/"
    return [
        Finding(level=f.level, subject=f.subject, message=f.message.replace(prefix, ""))
        for f in findings
    ]


def _copy_registry(source: Path, target: Path) -> None:
    """Copy the manifests a submission needs to resolve against.

    Commits are copied too: a submission may reference a pinned commit, and the
    store is what holds it.
    """
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
