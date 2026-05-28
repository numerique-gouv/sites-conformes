# Documentation sites-conformes

Documentation officielle de sites-conformes en français, construite avec Sphinx et le thème Wagtail.

## Build local

```bash
cd docs
pip install -r requirements.txt
make html
open _build/html/index.html  # Mac
```

## Structure

- `guide/` : guides d'utilisation (installation, configuration)
- `index.md` : page d'accueil
- `changelog.md` : pointeurs vers les releases GitHub

## Publication

La publication automatique (par exemple via GitHub Pages) n'est pas encore configurée. Construisez la documentation localement avec `make html` en attendant qu'une action CI dédiée soit ajoutée.

## Technologies

- [Sphinx](https://www.sphinx-doc.org/)
- [sphinx-wagtail-theme](https://github.com/wagtail/sphinx-wagtail-theme)
- [MyST Parser](https://myst-parser.readthedocs.io/) (support Markdown)
