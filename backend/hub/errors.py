"""Catalog errors. Every failure a registry author can cause derives from HubError."""


class HubError(Exception):
    """Base class for registry, resolution and check failures."""


class RefError(HubError):
    """A reference string does not follow the ``ns/name:selector`` grammar."""


class ManifestError(HubError):
    """A manifest file is missing, malformed, or violates a naming rule."""


class ResolutionError(HubError):
    """A reference cannot be resolved, or composing sources is contradictory."""


class StoreError(HubError):
    """The commit store is inconsistent: a snapshot's digest no longer matches."""
