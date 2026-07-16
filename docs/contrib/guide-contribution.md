# Guide de contribution

Merci de contribuer à Sites Conformes ! Cette page décrit d'abord **ce qu'on
attend d'une contribution** (les *guidelines*), puis les gestes courants du
développement quotidien : lancer les tests, gérer les dépendances, respecter le
style de code.

Pour mettre en place votre environnement de travail au préalable, voir
{doc}`installation-locale`. Le projet s'appuie sur [just](https://just.systems/)
pour lancer des séries de commandes (les *recettes*) : tapez `just` pour afficher
la liste complète.

## Nos principes

Une contribution prête à être intégrée respecte les points suivants :

- **Langue du code** : les identifiants (variables, fonctions, classes) **et les commentaires** sont écrits en anglais ; seuls les textes affichés à l'utilisateur sont en français, via les {doc}`traductions`.
- **Nommage et style** : conventions Python/Django standard (`snake_case` pour les fonctions et variables, `PascalCase` pour les classes). L'ordre des imports (isort) et le formatage (`black`, 119 colonnes) sont appliqués automatiquement par les [pre-commit hooks](style-pre-commit).
- **Tests** : toute fonctionnalité est couverte par des tests automatisés, et l'ensemble de la suite passe sans erreur.
- **Accessibilité** : l'application est conforme au [RGAA v4.1](https://accessibilite.numerique.gouv.fr/) — équivalents textuels, contrastes suffisants, navigation au clavier, balisage sémantique, utilisation à 200 % de zoom, formulaires correctement étiquetés.
- **Documentation** : la documentation technique et utilisateur est mise à jour si nécessaire.

Avant toute mise en production, l'ensemble est passé en revue via la
{doc}`definition-of-done`, qui détaille cette liste point par point.

## Proposer une contribution

1. Créez une **branche dédiée** à partir de `main`.
2. Développez en respectant les principes ci-dessus.
3. Vérifiez localement avant de soumettre : `just quality` (ruff + black), `pre-commit run --all-files`, puis `just test`.
4. Ouvrez une **pull request** sur le dépôt [numerique-gouv/sites-conformes](https://github.com/numerique-gouv/sites-conformes).

> ℹ️ Conventions de nommage des branches et format des messages de commit : *[à compléter].*

## Lancer les tests

Les tests unitaires se lancent avec `just test`.

Cela lance les tests en parallèle pour gagner du temps, mais en cas d’échec, il est possible de les lancer
séquentiellement via `just unittest`.

Vous pouvez également générer un rapport sur la couverture de tests :

```sh
just coverage
```

Pour toutes ces commandes, il est possible de cibler une application Django spécifique, par exemple :

```sh
just test sites_conformes.core
just unittest sites_conformes.blog
just coverage sites_conformes.events
```

## Commandes Django

Pour obtenir la liste des commandes Django disponibles :

```sh
uv run python manage.py
```

## Gestion des dépendances avec uv

Le projet utilise [uv](https://docs.astral.sh/uv/) pour gérer les dépendances de paquets Python et produire des *builds*
déterministes.

Pour installer le projet sans les dépendances de dev :

```sh
just init
```

Pour installer le projet avec les dépendances de dev :

```sh
just init-dev
```

Pour installer un nouveau paquet et l’ajouter aux dépendances :

```sh
uv add <paquet>
```

Pour un paquet ne servant que pour le développement, par exemple `debug-toolbar` :

```sh
uv add --dev <paquet>
```

## Configuration : le fichier `.env`

Le projet utilise [django-dotenv](https://github.com/jpadilla/django-dotenv) pour gérer les réglages propres à chaque environnement, qui ne peuvent pas être embarqués dans le dépôt git : configuration locale de chaque intervenant·e (par exemple les paramètres de connexion à la base) et configuration de production.

Pour surcharger la configuration locale de développement, créez un fichier `.env` à la racine du projet Django.
Cf. [le fichier `.env.example`](https://github.com/numerique-gouv/sites-conformes/blob/main/.env.example) pour l’exemple, et la {doc}`référence des variables d'environnement <../deploiement/variables-environnement>` pour le détail de chaque réglage.

En staging et en production, les variables d’environnement sont spécifiées directement sur Scalingo.

## Envoi de courriels en local

En local, vous pouvez visualiser dans le terminal les courriels dont le template n’est pas hébergé sur Brevo.
Pour cela, définissez la variable `EMAIL_BACKEND` à `django.core.mail.backends.console.EmailBackend` dans votre fichier `.env`.

La configuration des courriels transactionnels en production (SMTP) est décrite dans {doc}`../deploiement/variables-environnement`.

## CSS

Le projet utilise [le Système de design de l’État](https://www.systeme-de-design.gouv.fr/), par le biais de la librairie
[django-dsfr](https://github.com/numerique-gouv/django-dsfr).

Il est donc nécessaire d’utiliser autant que possible les classes spécifiques au Système de design de l’État dans le HTML.

(style-pre-commit)=

## Style de code et pre-commit

Nous utilisons `ruff` et `black` pour assurer un formatage cohérent du code sur l’ensemble du projet.

Pour vérifier son code, on peut intégrer le linter adapté à son IDE ou lancer la commande suivante :

```sh
just quality
```

Pour que cette vérification soit faite systématiquement, nous utilisons des *pre-commit hooks*.

Ils doivent être installés via :

```sh
pre-commit install
```

Il est possible de faire une passe manuelle sur l’ensemble du code via :

```sh
pre-commit run --all-files
```

## Outils d’audit optionnels

### cloc

La recette `just cloc` compte les lignes de code par application. Elle nécessite l’outil [`cloc`](https://github.com/AlDanial/cloc).

Installation sur macOS :

```sh
brew install cloc
```

Sur Debian/Ubuntu :

```sh
sudo apt install cloc
```
