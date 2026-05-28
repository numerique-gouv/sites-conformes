# Documentation sites-conformes

Bienvenue dans la documentation de **sites-conformes**, un gestionnaire de contenu basé sur Wagtail et le Système de design de l'État (DSFR).

:::{note}
Cette documentation concerne les fonctionnalités spécifiques à sites-conformes. Pour la documentation générale de Wagtail, consultez [docs.wagtail.org](https://docs.wagtail.org/).
:::

## Qu'est-ce que sites-conformes ?

sites-conformes est un package Python qui étend Wagtail pour créer des sites conformes au [Système de Design de l'État français (DSFR)](https://www.systeme-de-design.gouv.fr/).

**Fonctionnalités principales :**
- 📝 Modèles de pages pour blog, événements et contenu
- 🧭 Gabarits et menus adaptés au DSFR
- ♿ Accessibilité RGAA intégrée

L'édition de contenu repose sur les `StreamField` standards de Wagtail. Le
package fournit un ensemble de blocs DSFR (cartes, alertes, accordéons,
tableaux, héros, etc.) que `ContentPage` et les autres modèles utilisent
directement, sans système maison à apprendre.

```{toctree}
---
maxdepth: 2
caption: Documentation
---
guide/installation
guide/configuration
changelog
```

```{toctree}
---
maxdepth: 2
caption: Guides
---
guide/db-storage
guide/cas-pratique-annuaire
```

```{toctree}
---
maxdepth: 2
caption: Contribuer
---
contrib/git-blame-ignore-revs
```

## Démarrage rapide

```bash
# Installation
uv add sites-conformes

# Ajouter à INSTALLED_APPS
INSTALLED_APPS = [
    "sites_conformes",
    "sites_conformes.core",
    "sites_conformes.blog",
    "sites_conformes.events",
    # ...
]
```

[Voir le guide complet d'installation](guide/installation.md)

## Besoin d'aide ?

- 📖 [Documentation Wagtail](https://docs.wagtail.org/)
- 💬 [GitHub Discussions](https://github.com/numerique-gouv/sites-conformes/discussions)
- 🐛 [Signaler un bug](https://github.com/numerique-gouv/sites-conformes/issues)
