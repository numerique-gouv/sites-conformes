# Configuration file for the Sphinx documentation builder.

import sys
from pathlib import Path

project = "sites-conformes"
copyright = "2025, DINUM"
author = "DINUM"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from sites_conformes import __version__ as release
except Exception:
    release = "unknown"

extensions = [
    "sphinx_wagtail_theme",
    "myst_parser",  # For Markdown support
]

# MyST Parser configuration for Markdown support
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "fr"

html_theme = "sphinx_wagtail_theme"
html_static_path = ["_static"]
# TODO: point this at the canonical doc host once it is decided. Currently a
# personal preview; do NOT keep this URL when publishing on PyPI.
html_baseurl = "https://sites-conformes.fabien.cool/"

html_theme_options = {
    "project_name": "sites-conformes",
    "github_url": "https://github.com/numerique-gouv/sites-conformes/",
    "logo": "logo.svg",
    "logo_alt": "sites-conformes",
}

html_context = {
    "github_user": "numerique-gouv",
    "github_repo": "sites-conformes",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
