# Documentation Sites Conformes

Bienvenue dans la documentation technique de **Sites Conformes**, un gestionnaire de contenu basé sur Wagtail et le Système de design de l'État (DSFR).

:::{note}
**Cette documentation est réservée aux aspects techniques** : déploiement, exploitation, intégration et contribution.

Pour tout ce qui concerne l'**édition de contenu et l'usage du back-office** (créer des pages, gérer les menus, publier), rendez-vous sur [sites.beta.gouv.fr](https://sites.beta.gouv.fr/documentation/).

Pour la documentation générale de Wagtail, consultez [docs.wagtail.org](https://docs.wagtail.org/).
:::

## Qu'est-ce que Sites Conformes ?

Sites Conformes étend Wagtail pour créer des sites conformes au [Système de Design de l'État français (DSFR)](https://www.systeme-de-design.gouv.fr/).

**Fonctionnalités principales :**
- 📝 Modèles de pages pour blog, événements et contenu
- 🧭 Gabarits et menus adaptés au DSFR
- ♿ Accessibilité RGAA intégrée

L'édition de contenu repose sur les `StreamField` standards de Wagtail. L'outil
fournit une bibliothèque de blocs DSFR prêts à l'emploi (cartes, alertes,
accordéons, tableaux, héros, etc.), directement disponibles dans les modèles de
pages : les personnes qui rédigent assemblent leurs pages avec ces composants,
sans développement spécifique.

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

- 📝 [Documentation éditeur Sites Conformes](https://sites.beta.gouv.fr/documentation/) — créer et gérer les contenus depuis le back-office
- 📖 [Documentation Wagtail](https://docs.wagtail.org/) — le CMS sous-jacent
- 💬 [Salon Tchap Sites Faciles](https://www.tchap.gouv.fr/#/room/#sites-faciles:agent.dinum.tchap.gouv.fr) — échanger avec l'équipe et la communauté
- 🐛 [Signaler un bug](mailto:contact@sites.beta.gouv.fr) — écrire à `contact@sites.beta.gouv.fr`
