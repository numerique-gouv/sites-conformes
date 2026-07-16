# Avec Docker — 🔵 Confirmé

Le projet fournit un `Dockerfile`. Cette méthode encapsule l'application et ses dépendances dans des conteneurs, ce qui rend le déploiement reproductible d'une machine à l'autre. Elle suppose d'être à l'aise avec Docker et Docker Compose.

## Prérequis

- Docker et Docker Compose installés sur le serveur
- Git (pour cloner le dépôt)
- Un nom de domaine configuré (pour la production)

## Étapes

1. **Cloner le dépôt.**

2. **Créer un fichier `docker-compose.yml`** à la racine du projet (adapté à votre contexte : service web, base PostgreSQL, volumes).

3. **Générer une `SECRET_KEY`** (vous la collerez dans le `.env` à l'étape suivante) :

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copiez la valeur affichée dans le terminal.

4. **Créer et éditer le fichier `.env`** en vous basant sur `.env.example` :

```bash
cp .env.example .env
```

Ouvrez ensuite `.env` dans un éditeur de texte et **renseignez les variables**. Chaque variable s'écrit sur une ligne sous la forme `NOM=valeur` (sans espace autour du `=`, sans guillemets). À minima :

- `SECRET_KEY` : la valeur générée à l'étape 3
- `DATABASE_URL` : l'adresse de connexion à la base PostgreSQL
- `ALLOWED_HOSTS` et `HOST_URL` : votre/vos domaine(s)
- `USE_DOCKER=1` : pour que les recettes `just` s'exécutent à l'intérieur du conteneur web

Pour ajouter d'autres variables d'environnement, voir la {doc}`référence des variables d'environnement <variables-environnement>`.

5. **Construire et lancer les conteneurs** :

```bash
docker compose up -d --build
```

6. **Initialiser le site** :

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput --ignore="*.sass"
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py set_config
docker compose exec web python manage.py import_dsfr_pictograms
docker compose exec web python manage.py create_starter_pages
```

> 💡 Avec `USE_DOCKER=1` dans votre `.env`, vous pouvez remplacer la quasi-totalité de ces commandes par un seul `just deploy` (qui enchaîne migrations, fichiers statiques, pages de démarrage, gabarits, illustrations et indexation). Seul `createsuperuser` reste à lancer séparément, via `just createsuperuser` (ou son alias `just csu`).

## Mise à jour (Docker)

1. **Sauvegarder la base de données** (voir {doc}`../donnees/sauvegarde-restauration`).

2. **Récupérer la dernière version du code** :

```bash
git pull
```

3. **Reconstruire les images et relancer** :

```bash
docker compose up -d --build
```

4. **Appliquer les migrations et regénérer les fichiers statiques** :

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput --ignore="*.sass"
```

> 💡 Avec `USE_DOCKER=1`, la recette `just update` enchaîne la synchronisation des dépendances (`uv sync`) puis `just deploy`. Pratique pour une mise à jour complète en une commande.

> ⚠️ Si vous venez de faire une migration depuis un site en prod avec une base de données de prod pour le faire tourner en local, n'oubliez pas d'effectuer la commande `set_config` pour réécrire la valeur de `HOST_URL` en base.
