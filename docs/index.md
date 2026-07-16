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

## Par où commencer ?

- 🚀 **Mettre un site en ligne** → {doc}`deploiement/index` (Scalingo, serveur Linux, Docker…). C'est le cas le plus courant.
- 💾 **Sauvegardes et stockage des médias** → {doc}`donnees/index`.
- 📦 **Intégrer Sites Conformes à un projet Django existant** → {doc}`paquet/index`.
- 🛠️ **Contribuer au projet** → {doc}`contrib/index`.

```{toctree}
---
maxdepth: 2
---
deploiement/index
donnees/index
paquet/index
contrib/index
changelog
```

## Besoin d'aide ?

- 📖 [Documentation Wagtail](https://docs.wagtail.org/)
- 💬 [GitHub Discussions](https://github.com/numerique-gouv/sites-conformes/discussions)
- 🐛 [Signaler un bug](https://github.com/numerique-gouv/sites-conformes/issues)
