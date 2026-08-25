# Avec Docker — 🔵 Confirmé

Le projet fournit un `Dockerfile`. Cette méthode encapsule l’application et ses
dépendances dans des conteneurs, ce qui rend le déploiement reproductible d’une
machine à l’autre. Elle suppose d’être à l’aise avec Docker et Docker Compose.

:::{warning}
Le `Dockerfile` fourni est un **point de départ**, pas une image de
production clés en main. Le système de fichiers d’un conteneur est éphémère :
ne comptez pas dessus pour stocker les médias uploadés
(le `VOLUME` déclaré ne suffit pas en production).
Configurez un stockage externe pour les médias
(voir {doc}`../donnees/stockage-medias`) et durcissez l’image
selon votre contexte avant toute mise en production.
:::

## Prérequis

- Docker et Docker Compose installés sur le serveur
- Git (pour cloner le dépôt)
- Un nom de domaine configuré (pour la production)

## Étapes

1. **Cloner le dépôt.**

2. **Créer un fichier `docker-compose.yml`** à la racine du projet
(adapté à votre contexte : service web, base PostgreSQL, volumes).

3. **Générer une `SECRET_KEY`**
(Copiez la valeur affichée dans le terminal,
vous la collerez dans le `.env` à l’étape suivante) :

    ```sh
    python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    ```

4. **Créer et éditer le fichier `.env`** en vous basant sur `.env.example` :

    ```sh
    cp .env.example .env
    ```

    Ouvrez ensuite `.env` dans un éditeur de texte et **renseignez les variables**.
    Chaque variable s’écrit sur une ligne sous la forme `NOM=valeur`
    (sans espace autour du `=`, sans guillemets). À minima :

    - `SECRET_KEY` : la valeur générée à l’étape 3
    - `DATABASE_URL` : l’adresse de connexion à la base PostgreSQL
    - `HOST_URL` : votre domaine principal
    - `ALLOWED_HOSTS` votre domaine principal et les éventuels (sous-)domaines secondaires
    - `USE_DOCKER=1` : pour que les recettes `just` s’exécutent à l’intérieur du
    conteneur web

    Pour ajouter d’autres variables d’environnement, voir la
    {doc}`référence des variables d’environnement <variables-environnement>`.

5. **Construire et lancer les conteneurs** :

    ```sh
    docker compose up -d --build
    ```

6. **Initialiser le site** :

    ```sh
    docker compose exec web python manage.py migrate
    docker compose exec web python manage.py collectstatic --noinput --ignore="*.sass"
    docker compose exec web python manage.py createsuperuser
    docker compose exec web python manage.py set_config
    docker compose exec web python manage.py import_dsfr_pictograms
    docker compose exec web python manage.py create_starter_pages
    ```

    :::{tip}
    💡 Avec `USE_DOCKER=1` dans votre `.env`, vous pouvez remplacer la
    quasi-totalité de ces commandes par un seul `just deploy`
    (qui enchaîne migrations, fichiers statiques, pages de démarrage, gabarits,
    illustrations et indexation).

    Seul `createsuperuser` reste à lancer séparément,
    via `just createsuperuser` (ou son alias `just csu`).
    :::

## Indexation de la recherche

Les contenus des pages sont indexés pour permettre la recherche sur le site, par
la commande `update_index` (cf. la [documentation de Wagtail](https://docs.wagtail.org/en/stable/topics/search/indexing.html)).
Elle est déjà lancée par `just deploy` à chaque déploiement.

Il est recommandé d’y ajouter une **réindexation hebdomadaire**, pour corriger
d’éventuels écarts entre l’index et les contenus. Selon votre plateforme :

- **Si vous disposez de `cron` sur la machine hôte**, ajoutez-y une tâche qui
  exécute la commande dans le conteneur :

  ```text
  crontab -e
  # Ajouter (en adaptant le chemin du projet) :
  0 3 * * 0 cd /opt/sites-conformes && docker compose exec -T web python manage.py update_index
  ```

  > L’option `-T` désactive l’allocation d’un terminal : elle est indispensable
  > pour une exécution via cron, qui n’en dispose pas.

- **Sur un hébergement de type *container-as-a-service*** (où `cron` n’est
  souvent pas disponible), planifiez plutôt `python manage.py update_index` via
  l’ordonnanceur de tâches de votre plateforme (tâche programmée / *scheduled
  job*).

## Mise à jour (Docker)

1. **Sauvegarder la base de données** (voir {doc}`../donnees/sauvegarde-restauration`).

2. **Récupérer la dernière version du code** :

    ```sh
    git pull
    ```

3. **Reconstruire les images et relancer** :

    ```sh
    docker compose up -d --build
    ```

4. **Appliquer les migrations et regénérer les fichiers statiques** :

    ```sh
    docker compose exec web python manage.py migrate
    docker compose exec web python manage.py collectstatic --noinput --ignore="*.sass"
    ```

    :::{tip}
    Avec `USE_DOCKER=1`, la recette `just update` enchaîne la synchronisation
    des dépendances (`uv sync`) puis `just deploy`. Pratique pour une mise à jour
    complète en une commande.
    :::

    :::{warning}
    Si vous venez de faire une migration depuis un site en prod avec une base
    de données de prod pour le faire tourner en local, n’oubliez pas
    d’effectuer la commande `set_config` pour réécrire la valeur de
    `HOST_URL` en base.
