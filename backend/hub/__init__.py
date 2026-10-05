"""piighost catalog: a registry of regex patterns, pattern groups and pipeline configs.

The registry is a directory of TOML manifests (see docs/hub/manifest.md). Every
publishable object is frozen into a content-addressed commit, referenced as
``ns/name:<tag|commit>`` (see docs/hub/resolution.md). This package loads a
registry, freezes and resolves its objects, renders piighost pipelines from them,
and checks them (examples, backtracking bounds, vocabulary, immutability).
"""
