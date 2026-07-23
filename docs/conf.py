# Configuration file for the Sphinx documentation builder.

import tomllib
from pathlib import Path

project = "Sites Conformes"
copyright = "2025, DINUM"
author = "DINUM"


# Read the package version from sites_conformes/pyproject.toml so the doc
# header never drifts out of sync with the published package.
def _read_package_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "sites_conformes" / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


release = _read_package_version()

extensions = [
    "sphinx_wagtail_theme",
    "myst_parser",  # For Markdown support
    "sphinx_copybutton",  # "Copier" button on code blocks
]

# Ne pas copier les invites de shell ni les commentaires de sortie
copybutton_prompt_text = r"\$ "
copybutton_prompt_is_regexp = True

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
# Host de publication : GitHub Pages, déployé par .github/workflows/docs.yml.
# À mettre à jour si un domaine personnalisé (CNAME) est mis en place.
html_baseurl = "https://numerique-gouv.github.io/sites-conformes/"

html_theme_options = {
    "project_name": "Sites Conformes",
    # Le thème accole le nom du fichier source à cette URL : elle doit donc
    # pointer jusqu'au dossier des sources de la doc, pas à la racine du dépôt.
    "github_url": "https://github.com/numerique-gouv/sites-conformes/blob/main/docs/",
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
