# Contribuer à Sites-Conformes

## Installation

Une documentation détaillée de l’installation en local est disponible sur [ONBOARDING.md](./ONBOARDING.md).

```sh
git clone https://github.com/numerique-gouv/sites-faciles
cd sites-faciles
```

### Effectuer les tests

Les tests unitaires peuvent être lancés avec `just test`.

Cela lance les tests en parallèle pour gagner du temps, mais en cas d’échec, il est possible de les lancer
séquentiellement via `just unittest`

Vous pouvez également générer un rapport sur la couverture de tests :

```sh
just coverage
```

Pour toutes ces commandes, il est possible via `just` de cibler une application Django spécifique, par exemple :

```sh
just test content_manager
just unittest blog
just coverage events
```

## Définition du fini

Avant chaque mise en production, les intervenant·es sont prié·es de [passer cette liste en revue](./DOD.md).

## Commandes

Le projet utilise [just](https://just.systems/) pour gérer le lancement de séries de commandes spéfiques, appelées recettes.

Il est possible d’avoir une liste des recettes implémentées en tapant simplement `just`.

Pour les commandes Django spécifiquement, il est possible d’en obtenir la liste avec la commande

```sh
uv run python manage.py
```

## Gestion des dépendances avec uv

Le projet utilise [uv](https://docs.astral.sh/uv/) pour gérer les dépendances de paquets Python et produire des *builds*
déterministes.

Pour installer le projet sans les dépendances de dev :

```sh
just init
```

Pour installer le projet avec les dépendances de dev :

```sh
just init-dev
```


Pour installer un nouveau paquet et l’ajouter aux dépendances :

```sh
uv add <paquet>
```

Pour un paquet ne servant que pour le développement, par exemple `debug-toolbar` :

```sh
uv add --dev <paquet>
```

## Configuration locale, production

Le projet utilise [django-dotenv](https://github.com/jpadilla/django-dotenv) pour gérer les settings des différents environnements ne pouvant être embarquées dans le dépôt git.

Typiquement :

- configuration locale spécifique à chaque intervenant·e sur le projet, e.g paramètres de connexion à la base de données ;
- configuration de production.

Pour surcharger la configuration locale de développement, il est nécessaire de créer un fichier `.env` à la racine du projet Django.
Cf. [le fichier .env.example](./src/.env.example) pour l’exemple.

En staging et en production, les variables d’environment sont spécifiées directement sur Scalingo.

## CSS

Le projet utilise [Le Système de design de l’État](https://www.systeme-de-design.gouv.fr/), par le biais de la librairie
[django-dsfr](https://github.com/numerique-gouv/django-dsfr)

Il est donc nécessaire d’utiliser autant que possible les classes spécifiques au Système de design de l’État dans le HTML.

## Traduction : À propos des fichiers `.po` et `.mo`

Ce project utilise le [système de traduction de Django](https://docs.djangoproject.com/en/dev/topics/i18n/translation/).

Le texte dans le code est en anglais et la traduction qui s’affiche sur le site en français, se trouve dans le fichier
`.po` du dossier `locales`.

Pour générer la traduction dans le fichier `.po` :

```sh
just makemessages
```

Django utilise une version compilée du fichier `.po`, c’est le fichier `.mo` que l’on obtient avec :

```sh
uv run  python manage.py compilemessages
```

Il est recommandé d’utiliser [https://poedit.net/](Poedit) pour les traductions, afin de profiter de sa mémoire de traduction
basée sur celles déjà existantes. Il produit directement le fichier `.mo` à la sauvegarde, il n’est donc pas nécessaire de le
compiler manuellement.

## Linter de code / Code Style

Nous utilisons `ruff` et `black` pour assurer un formatage cohérent du code sur l’ensemble du projet.

Pour vérifier son code, on peut intégrer le linter adapté à son IDE et ou lancer la commande suivante :

```sh
just quality
```

Pour s’assurer que cette vérification est faite de manière systématique, nous utilisons des *pre-commit hooks*.

Ils doivent être installés via :

```sh
pre-commit install
```

Il est possible de faire une passe manuelle sur l’ensemble du code via

```sh
pre-commit run --all-files
```

## Déploiement

### Variables d’environnement

En production, les variables d’environment sont spécifiées directement sur [Scalingo](https://scalingo.com/).

### Envoi de courriels

Les courriels transactionnels sont envoyés via [Brevo](https://www.brevo.com/fr/).

En local vous avez la possibilité de visualiser les courriels dont le template n’est pas hébergé sur Brevo depuis le terminal.
Pour ce faire la variable `EMAIL_BACKEND` doit être définie avec `django.core.mail.backends.console.EmailBackend` dans votre fichier `.env`

### Fichiers media

Nous utilisons en production sur Scalingo un service d’« *Object Storage* » compatible avec l’API S3 pour le stockage de tous les fichiers medias.

En local, il est possible d’utiliser simplement le stockage de fichiers local (`FileSystemStorage`) en laissant vide la variable `S3_HOST` dans le fichier `.env`.
Il est alors conseillé de définir la variable `MEDIA_ROOT` (par exemple à "medias") pour éviter la création de plusieurs répertoires de médias à la racine.
