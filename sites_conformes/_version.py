# Single source of truth for the version, read both at build time (setuptools
# dynamic version, cf. pyproject.toml) and at runtime (sites_conformes/__init__.py).
# On release, .github/workflows/publish.yml resolves the number from the GitHub
# Release tag, writes it here, and commits this file back to main so every
# source-based deployment (Scalingo, internal server, Docker) picks it up.
# The value committed below is the local/dev fallback between releases.
__version__ = "4.1-rc3"
