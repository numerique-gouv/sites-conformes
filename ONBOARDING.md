# Onboarding tech

## Installation

Le projet peut se lancer en local ou avec Docker.

Dans le cas d’une installation en local, voir la section « Préparation de l’environnement de travail » ci-dessous.

### Dans tous les cas, copier les variables d’environnement

- Créer le fichier `.env` à partir de `.env.example`, avec une `SECRET_KEY` générée (un `.env` existant n’est jamais écrasé) :

```sh
just setup-env
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
git clone https://github.com/numerique-gouv/numerique-gouv-cms.git

# ou en ssh
git clone git@github.com:numerique-gouv/numerique-gouv-cms.git
```

Et rentrer dans le dossier du dépôt

```sh
cd numerique-gouv-cms
```

### Ajouter le remote `upstream`

Ce dépôt est pour l’instant un fork de [Sites Conformes](https://github.com/numerique-gouv/sites-conformes) (anciennement Sites Faciles). En attendant son passage à une dépendance au paquet `sites-conformes`, ajouter le dépôt d’origine comme remote `upstream`, pour comparer le code et suivre ses évolutions :

```sh
git remote add upstream git@github.com:numerique-gouv/sites-conformes.git
git fetch upstream
```

Si le remote `upstream` d’un clone existant pointe encore vers l’ancien dépôt `sites-faciles`, mettre son URL à jour :

```sh
git remote set-url upstream git@github.com:numerique-gouv/sites-conformes.git
git fetch upstream --prune
```

### PostgreSQL (base de données)

Avoir un PostgreSQL qui tourne en local (cf. procédure d’installation sur [Ubuntu](https://documentation.ubuntu.com/server/how-to/databases/install-postgresql/index.html) ou sur [Mac](https://postgresapp.com/).)

Créer l’utilisateur (avec les droits nécessaires aux scripts d’administration) et la base de données (vide pour l’instant) définis par `DATABASE_USER`, `DATABASE_PASSWORD` et `DATABASE_NAME` dans le `.env` :

```sh
just setup-db
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
HOST_URL=sites-faciles.localhost
HOST_PORT=8000
FORCE_SCRIPT_NAME="/pages"
ALLOWED_HOSTS=localhost,0.0.0.0,127.0.0.1,.localhost
CSRF_TRUSTED_ORIGINS="http://127.0.0.1:18000,http://localhost:18000,http://*.localhost:18000"
```

- On peut alors accéder au site via http:/sites-faciles.localhost:18000/pages/

## Gestion de la base de données et des médias

Un ensemble de scripts pour gérer la base de données et les fichiers médias, que ce soit ceux de la base locale de dev ou ceux de la production.

Ils sont regroupés dans la catégorie « [Dev DB and medias management] » de la commande `just`.

La gestion des sauvegardes locales nécessite de définir la variable `BACKUP_DIR` dans le fichier `.env`, en spécifiant un répertoire situé hors du projet Django pour ne pas risquer de commiter une sauvegarde par erreur.

La gestion des sauvegardes de production nécessite en plus de définir la variable `PROD_APP` (le nom de l’app Scalingo) dans le fichier `.env`.

Le nom de la base de données et les paramètres du bucket S3 (`S3_BUCKET_NAME`, `S3_LOCATION`, `S3_HOST`, `S3_KEY_ID`, etc.) sont lus directement dans les variables d’environnement de l’app Scalingo : il n’est plus nécessaire de les recopier dans le `.env`, mais il faut être connecté à la CLI Scalingo avec un compte ayant accès à l’app.

Il faut aussi installer deux dépendances : d’une part, la CLI de Scalingo, en suivant [la documentation d’installation](https://doc.scalingo.com/tools/cli/start) et [celle de connexion](https://doc.scalingo.com/tools/cli/introduction), pour pouvoir récupérer la dernière sauvegarde de la base de données et les variables d’environnement de l’app.

D’autre part, le paquet [rclone](https://rclone.org/) (via `apt install rclone`) pour gérer la récupération des fichiers média depuis un S3.

###  Données locales

Il est possible de faire une sauvegarde de la base de données et des fichiers médias de l’instance via

```sh
just backup-local
```

Il est fortement recommandé d’en faire un avant de remplacer ces données par celles de production, sinon elles seront perdues !

Les fichiers de sauvegarde sont nommés `sites-conformes-local-db-*.sql.gz` et `sites-conformes-local-medias-*.tar.gz`.

###  Récupération des données de production

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

Après la restauration d’une base de données, la commande `set_config` est lancée automatiquement pour adapter la configuration du site à l’environnement local.

### Retour arrière d’une app Scalingo

En cas de problème après une mise en production, il est possible de restaurer une sauvegarde de la base de données d’une app Scalingo et de redéployer le code correspondant :

```sh
just scalingo-rollback <app> [region] [ref]
```

- `region` vaut `osc-fr1` par défaut (passer `-` pour la garder tout en précisant une `ref`).
- Par défaut, `ref` est le code du dernier déploiement réussi avant la sauvegarde choisie.
- La variable `REPO_URL_BASE` doit pointer vers le dépôt de ce projet (`https://github.com/numerique-gouv/numerique-gouv-cms`, cf. `.env.example`), sinon c’est le code de sites-conformes qui sera déployé.
- Prérequis : la CLI Scalingo, `git`, `curl` et un `postgresql-client` dont la version correspond à celle du serveur.

⚠️ La base de données de l’app est **remplacée** par la sauvegarde. Le script demande de taper le nom de l’app pour confirmer, fait une sauvegarde de sécurité si la dernière date de plus de 6 heures, et arrête les conteneurs web pendant la restauration.

### Copie de la production vers la staging

Pour remplacer la base de données et les fichiers médias de l’app de staging par ceux de la production :

```sh
just descend-prod-to-staging
```

Pour ne copier que la base de données ou que les fichiers médias :

```sh
just descend-prod-to-staging --db-only
just descend-prod-to-staging --medias-only
```

- Les variables `PROD_APP` et `STAGING_APP` (nom de l’app Scalingo de staging) doivent être définies dans le `.env`, ainsi que `BACKUP_DIR` pour la copie de la base de données, sinon le script s’arrête immédiatement.
- Les régions valent `osc-fr1` par défaut ; elles peuvent être changées via `PROD_REGION` et `STAGING_REGION` (qui vaut `PROD_REGION` par défaut).
- Les secrets (URL de la base de staging, paramètres S3 des deux apps) sont lus dans les variables d’environnement Scalingo de chaque app.
- La base vient de la **dernière sauvegarde** Scalingo de la production (elle peut donc dater de quelques heures) ; le dump est conservé dans `BACKUP_DIR/prod-to-staging-<date>`.
- Après la restauration, `migrate` et `set_config` sont lancés sur la staging, pour appliquer ses migrations et lui redonner son nom d’hôte.
- Les médias sont synchronisés du bucket S3 de production vers celui de staging avec `rclone sync` : les fichiers présents uniquement sur la staging sont supprimés.
- Prérequis : la CLI Scalingo, `rclone` et un `postgresql-client` dont la version correspond à celle du serveur.
- `rclone sync` doit lister le bucket de destination : l’utilisateur S3 de la staging doit avoir le droit `s3:ListBucket` sur le bucket (ressource `arn:aws:s3:::<S3_BUCKET_NAME>`, sans `/*`), sinon la copie des médias échoue avec une erreur 403 « Access Denied ».
- Avant toute modification, le script vérifie les versions de PostgreSQL : la prod doit être au moins en version 15 et la staging au moins en version 18, la staging ne doit pas être plus ancienne que la prod, et le `pg_restore` local doit pouvoir lire le dump sans être plus récent que le serveur de staging (sinon il envoie des paramètres que le serveur ne connaît pas, comme `transaction_timeout`).
- La version de la prod est lue dans sa dernière sauvegarde : après une mise à jour de PostgreSQL sur la prod, il faut créer une nouvelle sauvegarde (le script indique la commande) ou attendre la suivante.

⚠️ Toutes les tables de la base de staging sont supprimées avant la restauration. Le script demande de taper le nom de l’app de staging pour confirmer, refuse de tourner si `PROD_APP` et `STAGING_APP` sont identiques ou si les deux apps partagent le même emplacement S3, et arrête les conteneurs web de la staging pendant la restauration.

## Mise à jour de TarteAuCitron

La bibliothèque [TarteAuCitron](https://tarteaucitron.io/) est embarquée dans `static/lib/tarteaucitronjs/`. Pour la resynchroniser avec la version du paquet npm (définie dans `package-lock.json`) :

```sh
just sync-tarteaucitron
```

Cette recette est aussi lancée par `just upgrade`.
