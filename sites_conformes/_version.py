# Single source of truth for the version, read both at build time (setuptools
# dynamic version, cf. pyproject.toml) and at runtime (sites_conformes/__init__.py).
# Bumped by the "Prepare release" workflow, which opens a PR setting the value
# below. Once merged, every source-based deployment (Scalingo, internal server,
# Docker) picks it up, and publish.yml checks it against the release tag before
# publishing to PyPI. The value below is the local/dev fallback between releases.
__version__ = "0.0.0.dev0"
