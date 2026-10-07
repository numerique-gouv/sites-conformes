# Single source of truth for the version, read both at build time (setuptools
# dynamic version, cf. pyproject.toml) and at runtime (sites_conformes/__init__.py).
# Bump this by hand and commit it before cutting the matching GitHub Release;
# source-based deployments (Scalingo, internal server, Docker) read it straight
# from here.
__version__ = "4.2.0"
