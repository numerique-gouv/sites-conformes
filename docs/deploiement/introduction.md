# Avant de commencer

## Prérequis

Sites Conformes est basé sur Django/Wagtail et nécessite :

- **Python** 3.12 à 3.14
- **PostgreSQL** 14 à 17
- Un espace de **stockage** pour les fichiers médias (local ou object storage S3)
- un serveur web WSGI ou ASGI, par exemple Gunicorn + Nginx (Scalingo prend automatiquement en charge cet aspect)
- un nom de domaine (pas forcément nécessaire au moment du déploiement initial, cela peut être changé à tout moment).

## Le dépôt et les branches

Le dépôt GitHub présentant la version officielle de Sites Conformes est celui-ci : <https://github.com/numerique-gouv/sites-conformes>

La branche `main` correspond à la branche présentant les développements en cours. La branche `production` est la branche à déployer sur les instances. Elle est mise à jour à chaque release.

Les releases sont à suivre [ici](https://github.com/numerique-gouv/sites-conformes/releases).

## Les niveaux

Chaque méthode de déploiement porte un badge indiquant le niveau technique attendu. Ce n'est pas une note d'intelligence : c'est une estimation du temps et des compétences système nécessaires.

| Badge | Niveau | Pour qui ? |
| --- | --- | --- |
| 🟢 **Débutant** | Pas (ou peu) d'administration système. On suit les étapes, l'hébergeur s'occupe du reste. | Agent, webmestre, développeur·se peu familier·e des serveurs Linux. |
| 🔵 **Confirmé** | À l'aise avec la ligne de commande Linux, les services système, les bases de données. | Développeur·se ou administrateur·rice système. |
| 🟣 **Expert** | Bonne connaissance de l'administration système et des environnements virtuels. | Développeur·se ou administrateur·rice système. |

## Deux outils que vous croiserez partout

- `uv` est un gestionnaire de paquets et d'environnements Python (un remplaçant rapide de `pip` + `venv`). C'est l'outil utilisé par le projet. Quand vous voyez `uv sync`, cela installe les dépendances décrites dans le fichier `pyproject.toml` / `uv.lock`, l'équivalent moderne de `pip install -r requirements.txt`.
- `just` est un lanceur de commandes (un « raccourcisseur »). Le projet fournit un fichier `justfile` qui regroupe des recettes prêtes à l'emploi. Au lieu de taper une longue suite de commandes Django, vous tapez par exemple `just deploy`. Pour voir toutes les recettes disponibles : `just`.
