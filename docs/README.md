---
orphan: true
---

# Documentation Sites Conformes

Documentation technique officielle de Sites Conformes en français, construite avec Sphinx et le thème Wagtail.

## Build local

Depuis la racine du dépôt :

```bash
just docs        # build + serveur local à rechargement auto (ouvre le navigateur)
just docs-build  # build ponctuel, HTML dans docs/_build/html/
```

## Structure

- `index.md` : page d'accueil
- `deploiement/` : déployer une instance (Scalingo, serveur Linux, Docker, migration…)
- `donnees/` : base de données et médias (sauvegarde, restauration, stockage)
- `paquet/` : utiliser Sites Conformes comme package Django
- `contrib/` : développer et contribuer (installation locale, architecture, guide de contribution…)
- `changelog.md` : pointeurs vers les releases GitHub

## Publication

La documentation est publiée automatiquement sur **GitHub Pages** à
<https://numerique-gouv.github.io/sites-conformes/>, via le workflow
`.github/workflows/docs.yml` (déclenché à chaque push sur `main` touchant `docs/`).

## Technologies

- [Sphinx](https://www.sphinx-doc.org/)
- [sphinx-wagtail-theme](https://github.com/wagtail/sphinx-wagtail-theme)
- [MyST Parser](https://myst-parser.readthedocs.io/) (support Markdown)
