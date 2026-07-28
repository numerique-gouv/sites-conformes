# Guide de contribution

Ce guide décrit **comment contribuer à Sites Conformes** : ce qu'on attend d'une
contribution, le processus pour la proposer, et les conventions de code à
respecter.

La mise en place de l'environnement de développement (outils, dépôt,
configuration, base de données) est décrite à part, dans
{doc}`installation-locale`.

## Nos principes

Une contribution prête à être intégrée respecte les points suivants :

- **Langue du code** : les identifiants (variables, fonctions, classes) **et les commentaires** sont écrits en anglais ; seuls les textes affichés à l'utilisateur sont en français, via les {doc}`traductions`.
- **Nommage et style** : conventions Python/Django standard (`snake_case` pour les fonctions et variables, `PascalCase` pour les classes). L'ordre des imports (isort) et le formatage (`black`, 119 colonnes) sont appliqués automatiquement par les [pre-commit hooks](style-pre-commit).
- **Tests** : toute fonctionnalité est couverte par des tests automatisés, et l'ensemble de la suite passe sans erreur.
- **Accessibilité** : l'application est conforme au [RGAA v4.1](https://accessibilite.numerique.gouv.fr/) — équivalents textuels, contrastes suffisants, navigation au clavier, balisage sémantique, utilisation à 200 % de zoom, formulaires correctement étiquetés.
- **CSS** : utilisez autant que possible les classes du [Système de design de l'État](https://www.systeme-de-design.gouv.fr/) (via [django-dsfr](https://github.com/numerique-gouv/django-dsfr)) plutôt que du style maison.
- **Documentation** : la documentation technique et utilisateur est mise à jour si nécessaire.

Avant toute mise en production, l'ensemble est passé en revue via la
{doc}`definition-of-done`, qui détaille cette liste point par point.

## Proposer une contribution

1. Créez une **branche dédiée** à partir de `main`, nommée `<votre-identifiant>/<description-courte>` — l'identifiant est votre nom d'utilisateur GitHub (ou vos initiales), et la description est en anglais, en minuscules avec des tirets. Exemple : `lucie/fix-breadcrumb-rgaa`.
2. Développez en respectant les principes ci-dessus.
3. Vérifiez localement avant de soumettre : `just quality` (ruff + black), `pre-commit run --all-files`, puis `just test`.
4. Ouvrez une **pull request** sur le dépôt [numerique-gouv/sites-conformes](https://github.com/numerique-gouv/sites-conformes). GitHub pré-remplit la description avec le [modèle de PR](https://github.com/numerique-gouv/sites-conformes/blob/main/.github/PULL_REQUEST_TEMPLATE) du dépôt : complétez-le. Rédigez le **titre en français** — il sert à générer les notes de version (*release notes*) en français.
5. Une fois la PR prête, **assignez un·e relecteur·rice** : Sylvain ou Lucie.

> ℹ️ **Messages de commit** : rédigez un message court et explicite. Il n'y a pas de format strict imposé. Les *pull requests* sont généralement intégrées en *squash*, avec ajout automatique du numéro de PR.

## Échanger entre développeurs

Si vous souhaitez contribuer activement, faites-nous signe pour rejoindre notre
**canal Tchap dédié aux développeurs**, où l'on discute des évolutions et des
besoins de Sites Conformes.

Contactez l'équipe à [contact@sites.beta.gouv.fr](mailto:contact@sites.beta.gouv.fr)
ou depuis le [salon Tchap public](https://www.tchap.gouv.fr/#/room/#sites-faciles:agent.dinum.tchap.gouv.fr)
pour y être ajouté·e.

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

## Ajouter une dépendance

Le projet gère ses dépendances avec [uv](https://docs.astral.sh/uv/) (fichiers `pyproject.toml` et `uv.lock`).

Pour ajouter un paquet :

```sh
uv add <paquet>
```

Pour un paquet ne servant qu'au développement, par exemple `debug-toolbar` :

```sh
uv add --dev <paquet>
```

Pensez à committer le `uv.lock` mis à jour avec votre modification.

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
