# Installer le projet en local

Cette page met en place un environnement de développement sur votre machine. Les
étapes se suivent **dans l'ordre** : installer les outils, cloner le dépôt,
configurer, préparer la base de données, puis lancer le site.

Deux approches sont possibles :

- **En natif** (méthode utilisée par l'équipe de Sites Conformes) — les étapes ci-dessous ;
- **Avec Docker** — une alternative auto-suffisante décrite en fin de page.

> ℹ️ Les commandes système sont données pour Ubuntu/Debian ; adaptez-les à votre
> système (macOS avec Homebrew, etc.).

## Les outils du projet

Le projet s'appuie sur deux outils que vous rencontrerez partout :

- **[`uv`](https://docs.astral.sh/uv/)** — gestionnaire de paquets et
  d'environnements Python (un remplaçant rapide de `pip` + `venv`). Il installe
  les dépendances aux versions exactes verrouillées dans `uv.lock`, outils de
  développement compris.
- **[`just`](https://just.systems/)** — lanceur de commandes. Le fichier
  `justfile` regroupe des *recettes* qui enchaînent des commandes Django/uv.
  Tapez `just` pour afficher la liste complète.
- **[`pre-commit`](https://pre-commit.com/)** — vérifie et formate
  automatiquement votre code (`ruff`, `black`) à chaque `git commit`. Les *hooks*
  sont installés par `just init-dev` ; sinon, lancez `pre-commit install` une
  fois le projet installé.

> ⚠️ **N'oubliez pas d'installer les *pre-commit hooks*.** Sans eux, rien ne
> formate votre code localement, et le **contrôle qualité de la CI échouera** :
> l'intégration continue rejoue `pre-commit` et `just quality` (ruff + black) sur
> l'ensemble des fichiers, et bloque la *pull request* au moindre écart de
> formatage.

> 🔧 **Si vous ne voulez pas installer ces outils**
>
> - **Sans `just`** : chaque recette n'est qu'un raccourci. Vous pouvez lancer
>   directement les commandes sous-jacentes — les équivalents sont indiqués aux
>   étapes concernées.
> - **Sans `uv`** : possible avec `pip` + `venv`, mais vous perdez le
>   verrouillage exact des versions. `uv` reste fortement recommandé en
>   développement. Si vous utilisez `uv`, pensez à mettre `USE_UV=1` dans votre
>   `.env` (voir plus bas) pour que les recettes `just` préfixent les commandes
>   par `uv run`.

## Prérequis

Installer :

- [Python 3](https://www.python.org/) (normalement déjà installé sur un système moderne)
- [git](https://git-scm.com/)
- [pipx](https://pipx.pypa.io/stable/)
- [uv](https://docs.astral.sh/uv/)
- [just](https://just.systems/)
- [npm](https://docs.npmjs.com/)
- [gettext](https://www.gnu.org/software/gettext/gettext.html)

Sous Ubuntu :

```sh
sudo apt install -y git python3 pipx just gettext
pipx ensurepath
pipx install uv
```

## Cloner le dépôt

```sh
git clone https://github.com/numerique-gouv/sites-conformes.git

# ou en ssh
git clone git@github.com:numerique-gouv/sites-conformes.git
```

Puis entrez dans le dossier du dépôt :

```sh
cd sites-conformes
```

## Configurer l'environnement (`.env`)

Les réglages locaux se placent dans un fichier `.env` à la racine du projet.
Copiez le modèle fourni :

```sh
cp .env.example .env
```

Générez une `SECRET_KEY` :

```sh
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Puis renseignez dans `.env` au moins :

- `SECRET_KEY` — la valeur générée ci-dessus ;
- `DEBUG=True` ;
- `HOST_PROTO=http` ;
- `USE_UV=1` si vous utilisez `uv` (pour que les recettes `just` passent par `uv run`).

La liste complète des réglages est décrite dans
{doc}`../deploiement/variables-environnement`.

## Préparer la base de données (PostgreSQL)

Avoir un PostgreSQL qui tourne en local (procédure d'installation sur
[Ubuntu](https://documentation.ubuntu.com/server/how-to/databases/install-postgresql/index.html)
ou sur [Mac](https://postgresapp.com/)).

Créez l'utilisateur et la base :

```sh
# utilisateur avec les droits nécessaires aux scripts d'administration
psql -c "CREATE USER sitesconformes WITH CREATEDB LOGIN PASSWORD 'votre_mot_de_passe';" -U postgres

# base de données (vide pour l'instant)
psql -c "CREATE DATABASE sitesconformes OWNER sitesconformes;" -U postgres
```

Renseignez les paramètres de connexion correspondants dans votre `.env`.

## Installer et initialiser le projet

Une seule commande installe les dépendances (dont celles de développement), lance
les migrations, collecte les fichiers statiques, crée les pages de démarrage et
installe les *pre-commit hooks* :

```sh
just init-dev
```

> 🔧 **Sans `just`** — lancez les étapes manuellement (préfixez par `uv run` si
> vous utilisez `uv`, ou activez d'abord votre `venv`) :
>
> ```sh
> uv sync
> python manage.py migrate
> python manage.py collectstatic --noinput
> python manage.py create_starter_pages
> python manage.py import_page_templates
> python manage.py import_illustration_images
> python manage.py update_index
> pre-commit install
> ```

## Créer un compte administrateur

```sh
just createsuperuser
```

> 🔧 **Sans `just`** : `python manage.py createsuperuser`.

## Lancer le serveur

```sh
just runserver
```

Le site est alors accessible sur <http://localhost:8000>, et l'administration sur
<http://localhost:8000/cms-admin/>.

> 🔧 **Sans `just`** : `python manage.py runserver localhost:8000`.

> 💡 Pour lister les commandes de gestion Django disponibles : `uv run python manage.py`.

## Avec Docker

Alternative auto-suffisante : le projet fournit un `docker-compose.yml`. Après
avoir copié le `.env` (voir ci-dessus) et ajouté `USE_DOCKER=1`, lancez les
conteneurs :

```sh
docker compose up
```

Avec `USE_DOCKER=1`, les recettes `just` s'exécutent à l'intérieur du conteneur
web : vous pouvez donc initialiser le site avec `just init-dev` puis créer un
compte avec `just createsuperuser`, comme en natif.

## Options avancées

### Courriels en local

Par défaut, les courriels tentent de partir réellement. En développement, vous
pouvez les afficher dans le terminal plutôt que de les envoyer, en réglant dans
votre `.env` :

```sh
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Stockage S3 local avec MinIO

[MinIO](https://min.io/) simule un stockage objet compatible S3 en local, utile
pour tester la configuration de production sans vrai bucket S3.

Lancez MinIO :

```sh
docker run -d \
  --name minio \
  -p 9000:9000 \
  -p 9001:9001 \
  -v ~/minio-data:/data \
  -e MINIO_ROOT_USER=admin \
  -e MINIO_ROOT_PASSWORD=password123 \
  quay.io/minio/minio server /data --console-address ":9001"
```

Accédez à la console sur <http://localhost:9001> (identifiants `admin` /
`password123`) et créez un bucket (par exemple `sc-local`). Pour éviter les URLs
signées (plus simple en local), rendez-le public : _Buckets → sc-local →
Anonymous → Add Access Rule → Prefix `/`, Access `readonly`_.

Ajoutez ensuite dans votre `.env` :

```sh
S3_HOST=host.docker.internal:9000
S3_PUBLIC_HOST=localhost:9000
S3_PROTOCOL=http
S3_KEY_ID=admin
S3_KEY_SECRET=password123
S3_BUCKET_NAME=sc-local
S3_BUCKET_REGION=
S3_LOCATION=medias/
```

> **Note :** c'est la variable `S3_HOST` qui active le stockage S3. Sans elle, les
> médias sont stockés sur le système de fichiers local, quelle que soit la
> configuration MinIO.

## Gestion de la base de données et des médias

La sauvegarde, la récupération des données de production et la restauration sont
décrites dans {doc}`../donnees/sauvegarde-restauration`.
