# Onboarding tech

## Installation

Le projet peut se lancer en local ou avec Docker.

Dans le cas d’une installation en local, voir la section « Préparation de l’environnement de travail » ci-dessous.

### Dans tous les cas, copier les variables d’environnement

- Copier le fichier

```sh
cp .env.example .env
```

- Générer la `SECRET_KEY`

```sh
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

- Mettre les valeurs pertinentes dans le fichier `.env`, notamment :
  - `DEBUG=True`
  - `HOST_PROTO=http`

### En local

#### Variables d’environnement

- mettre la variable d’environnement `USE_UV` à `1` dans le fichier `.env`
- il est possible de configurer l’envoi des emails vers la console Django (cf. [CONTRIBUTING.md](./CONTRIBUTING.md))

#### Installer le projet

- La commande suivante installe les dépendances, fait les migrations et collecte les fichiers

```sh
just init-dev
```

#### Créer un utilisateur

- La commande suivante crée un utilisateur administrateur avec tous les droits:

```sh
just createsuperuser
```

#### Lancer le serveur

```sh
just runserver
```

### via Docker

#### Lancer les containers

```sh
docker compose up
```

## Préparation de l’environnement de travail

Procédure testée sous Ubuntu.

### Prérequis

Installer :

- [Python 3](https://www.python.org/) (normalement déjà installé sur un système moderne)
- [git](https://git-scm.com/)
- [pipx](https://pipx.pypa.io/stable/)
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)
- [npm](https://docs.npmjs.com/)
- [gettext](https://www.gnu.org/software/gettext/gettext.html)

Sous Ubuntu, la commande pour cela est :

```sh
sudo apt install -y git python3 pipx just gettext
pipx ensurepath
pipx install uv
```

### Cloner le dépôt

```sh
git clone https://github.com/numerique-gouv/sites-faciles.git

# ou en ssh
git clone git@github.com:numerique-gouv/sites-faciles.git
```

Et rentrer dans le dossier du dépôt

```sh
cd sites-faciles
```

### PostgreSQL (base de données)

Avoir un PostgreSQL qui tourne en local (cf. procédure d’installation sur [Ubuntu](https://documentation.ubuntu.com/server/how-to/databases/install-postgresql/index.html) ou sur [Mac](https://postgresapp.com/).)

```sh
# créer un utilisateur avec les droits nécessaires aux scripts d’administration
psql -c "CREATE USER sitesconformes WITH CREATEDB LOGIN PASSWORD 'votre_mot_de_passe';" -U postgres


# créer la base de données (vide pour l’instant)
psql -c "CREATE DATABASE sitesconformes OWNER sitesconformes;" -U postgres
```

## Fonctionnement depuis un sous-répertoire

Lorsque la variable `FORCE_SCRIPT_NAME` est configurée, le site tourne dans un sous-répertoire, fonctionnalité qui n’est pas gérée par le serveur de développement de base de Django (`runserver`).

Pour tester le fonctionnement en local, il faut donc passer par [gunicorn](https://gunicorn.org/) et [nginx](https://nginx.org/). À cette fin :

- Installer nginx si ce n'est pas déjà fait : <https://nginx.org/en/docs/install.html>
- Après avoir configuré les variables d’environnement (cf. ci-dessus), lancer la commande suivante pour générer et mettre en place la configuration nginx :

```sh
just nginx-generate-config-file
```

- Lancer le serveur local via gunicorn avec la commande suivante (à la place de `just runserver` donc) :

```sh
just run_gunicorn
```

- Accéder au site via nginx en ajoutant 1 au port utilisé par gunicorn. Par exemple, si le `.env` contient les valeurs suivantes :

```sh
DEBUG=False
HOST_PROTO=http
HOST_URL=sites-conformes.localhost
HOST_PORT=8000
FORCE_SCRIPT_NAME="/pages"
ALLOWED_HOSTS=localhost,0.0.0.0,127.0.0.1,.localhost
CSRF_TRUSTED_ORIGINS="http://127.0.0.1:18000,http://localhost:18000,http://*.localhost:18000"
```

- On peut alors accéder au site via http:/sites-conformes.localhost:18000/pages/

## Gestion de la base de données et des médias

Un ensemble de scripts pour gérer la base de données et les fichiers médias, que ce soit ceux de la base locale de dev ou ceux de la production.

Ils sont regroupés dans la catégorie « [Dev DB and medias management] » de la commande `just`.

La gestion des sauvegardes locales nécessite de définir la variable `BACKUP_DIR` dans le fichier `.env`, en spécifiant un répertoire situé hors du projet Django pour ne pas risquer de commiter une sauvegarde par erreur.

La gestion des sauvegardes de production nécessite de définir les variables supplémentaires dans le fichier `.env`.

Il faut aussi installer deux dépendances : d’une part, la CLI de Scalingo, en suivant [la documentation d’installation](https://doc.scalingo.com/tools/cli/start) et [celle de connexion](https://doc.scalingo.com/tools/cli/introduction), pour pouvoir récupérer la dernière sauvegarde de la base de données.

D’autre part, le paquet [rclone](https://rclone.org/) (via `apt install rclone`) pour gérer la récupération des fichiers média depuis un S3.

```sh
PROD_APP= (le nom de l’app Scalingo, par ex sites-conformes)
PROD_DB_NAME= (le nom de la base de données dans Scalingo, par ex sites_facil_123)
PROD_S3_BUCKET_NAME=
PROD_S3_LOCATION=
RCLONE_CONFIG_MYS3_REGION_NAME=
RCLONE_CONFIG_MYS3_ENDPOINT=
RCLONE_CONFIG_MYS3_ACCESS_KEY_ID=
RCLONE_CONFIG_MYS3_SECRET_ACCESS_KEY=
RCLONE_CONFIG_MYS3_PROVIDER=Other
RCLONE_CONFIG_MYS3_TYPE="s3"
```

- Le préfixe `RCLONE_CONFIG_MYS3_*` permet à `rclone` de récupérer automatiquement ces paramètres depuis les variables d’environnement.

### Données locales

Il est possible de faire une sauvegarde de la base de données et des fichiers médias de l’instance via

```sh
just backup-local
```

Il est fortement recommandé d’en faire un avant de remplacer ces données par celles de production, sinon elles seront perdues !

### Récupération des données de production

Pour récupérer la base de données et les fichiers média de production en local, taper la commande suivante :

```sh
just descend-prod
```

### Restauration

Il est possible de restaurer les données locales ou de production via, respectivement,

```sh
just restore-local
```

et

```sh
just restore-prod
```
