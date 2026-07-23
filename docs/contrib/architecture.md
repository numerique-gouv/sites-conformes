# Architecture du projet

[![Made with Django](https://img.shields.io/badge/Made%20with-Django-0C4B33.svg)](https://www.djangoproject.com/)
[![Made with Wagtail](https://img.shields.io/badge/Made%20with-Wagtail-0F7676.svg)](https://wagtail.io/)

Sites Conformes est développé en utilisant le framework [Django](https://www.djangoproject.com/) et le CMS [Wagtail](https://wagtail.org/). Il est centré autour d'une application principale nommée **sites_conformes.core**, accompagnée d’applications annexes pour divers types de pages :

## Applications Django

- **sites_conformes.core** : l’application principale, contient les contenus communs, les pages standard (pages de contenu), les pages d’index de catalogue et la gestion des configurations
- **blog** : Permet de gérer des articles de blog et des index de blog, et les flux RSS correspondants.
- **dashboard** : Contient les personnalisations des panneaux d’administration de Wagtail (dans `templates/wagtailadmin` et `wagtail_hooks.py`)
- **[django-dsfr](https://github.com/numerique-gouv/django-dsfr)** : Permet d’utiliser facilement le [système de design de l’État](https://www.systeme-de-design.gouv.fr/) dans des templates Django.
- **events** : Similaire à `blog`, mais permet de gérer des événements et des pages de calendrier, ainsi que les exports iCal correspondants.
- **forms** : implémentation du [module de création de formulaire](https://docs.wagtail.org/en/stable/reference/contrib/forms/index.html) de Wagtail, par exemple pour les pages de contact. Volontairement assez limité (suffisant pour un formulaire de contact mais pas beaucoup plus), pour les cas complexes il vaut mieux privilégier l’intégration de [Démarches simplifiées](https://www.demarches-simplifiees.fr) ou de [Grist](https://grist.numerique.gouv.fr/).
- **db_storage** : stockage des médias en base de données PostgreSQL, alternative au S3 pour les PaaS avec filesystem éphémère (cf. {doc}`../donnees/stockage-medias`)
- **proconnect** : permet la connexion via [ProConnect](https://www.proconnect.gouv.fr/)

## Structure du dépôt

En plus des applications déjà citées, le dépôt contient les répertoires suivants :

- **config** : le projet Django proprement dit
- **locale** : la traduction des templates de base et du JS global du site (cf. {doc}`traductions`). La localisation des apps listées plus haut se fait à l’intérieur de celles-ci.
- **scripts** : scripts shell utilisés par certaines commandes et fichiers de configurations associés.
- **static** : des fichiers statiques communs à l’ensemble du site (CSS global, JS global, quelques images intégrées par défaut) ainsi que la librairie tierce TarteaucitronJS (utilisée pour la gestion des cookies tiers)
- **templates** : les templates de base du site.

## Schéma

```{image} ../_static/sites-conformes-schema.svg
:alt: Schéma montrant les apps listées ci-dessus ainsi que l’interconnection avec la BDD, le S3 et les services tiers (dont ProConnect)
```

Schéma de l’application dans le cas d’un hébergement sur Scalingo.

## Indexation des contenus

Les contenus des pages sont indexés pour la recherche par un script `python manage.py update_index` (cf. [documentation de Wagtail](https://docs.wagtail.org/en/stable/topics/search/indexing.html)).

Le lancement automatique et périodique de ce script en production est décrit dans {doc}`../deploiement/serveur-linux`.
