# Sur un serveur Linux (VPS, dédié ou interne) — 🔵 Confirmé

Le déploiement sur VPS ou sur un serveur interne vous donne un contrôle complet sur l'environnement. C'est adapté si votre administration gère ses propres serveurs ou utilise un hébergeur comme OVH ou Scaleway.

> ℹ️ **VPS managé ou non ?** Sur un VPS « classique » (OVH, Scaleway…) **non infogéré**, vous gérez tout l'intérieur de la machine : c'est le cas couvert ci-dessous. Si vous disposez d'une offre **infogérée**, la maintenance système est assurée par le prestataire et vous pouvez sauter l'étape 1.

## Prérequis

- Un VPS ou serveur sous Linux (Ubuntu 22.04+ ou Debian 12+ recommandé)
- Accès root ou sudo
- Un nom de domaine configuré (enregistrement DNS de type `A` pointant vers l'IP du serveur)

## Étape 1 — Installation des dépendances système (si nécessaire)

> Étape à effectuer sur un serveur **non infogéré**. Sur une offre infogérée, passez à l'étape 2.

Mettez à jour le système puis installez les paquets nécessaires : Python, PostgreSQL, Nginx, Git et les outils de compilation requis par certaines dépendances Python.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  python3 python3-venv python3-dev \
  postgresql postgresql-contrib \
  nginx git \
  build-essential libpq-dev
```

- `python3-venv` permet de créer des environnements virtuels.
- `libpq-dev` et `build-essential` sont nécessaires pour compiler `psycopg` (le pilote PostgreSQL de Python).
- `postgresql-contrib` ajoute des extensions utiles à PostgreSQL.

## Étape 2 — Mise en place de la base de données

Création d'une base de données PostgreSQL avec les droits correspondants :

```text
sudo -u postgres psql
CREATE USER sites_conformes WITH PASSWORD 'mot_de_passe_solide';
CREATE DATABASE sites_conformes_db OWNER sites_conformes;
\q
```

## Étape 3 — Déploiement de l'application

Clonez le dépôt (par exemple dans `/opt/sites-conformes`), installez les dépendances, configurez l'environnement, puis initialisez le site. Voici les **deux voies possibles**, côte à côte.

### Voie A — uv + just *(voie officielle du projet)*

```bash
cd /opt/sites-conformes
git clone https://github.com/numerique-gouv/sites-conformes.git .
git checkout production
# Installer uv si nécessaire : https://docs.astral.sh/uv/
# Éditer le .env (voir modèle ci-dessus)
# Installation des dépendances + initialisation complète du site
just init
# (just init = `uv sync --no-group dev` puis `just deploy`)
# Création du compte administrateur
just createsuperuser
```

`just init` installe les dépendances de production puis lance `just deploy`, qui enchaîne : `migrate`, `collectstatic`, `create_starter_pages`, `import_page_templates`, `import_illustration_images` et l'indexation (`update_index`).

### Voie B — pip + venv *(voie classique)*

```bash
cd /opt/sites-conformes
git clone https://github.com/numerique-gouv/sites-conformes.git .
git checkout production
# Environnement virtuel + dépendances
python3 -m venv venv          # création de l'environnement virtuel
source venv/bin/activate      # activation de l'environnement virtuel
pip install .                 # dépendances déclarées dans pyproject.toml
# Éditer le .env
# Initialisation manuelle du site
python manage.py migrate
python manage.py collectstatic --noinput --ignore="*.sass"
python manage.py createsuperuser
python manage.py set_config
python manage.py create_starter_pages
python manage.py import_page_templates
python manage.py import_illustration_images
python manage.py update_index
```

> ⚠️ Le projet est aujourd'hui outillé autour de `uv` (fichiers `pyproject.toml` et `uv.lock`) et **ne fournit pas de** `requirements.txt`. La voie A (uv + just) est donc la référence et garantit des versions de dépendances identiques à celles testées par l'équipe. La voie B (pip) reste possible via `pip install .`, mais elle est surtout utile à titre pédagogique ou dans les environnements où `uv` n'est pas disponible.

Pour la liste complète des réglages à mettre dans le `.env`, voir la {doc}`référence des variables d'environnement <variables-environnement>`.

## Étape 4 — Configurer un serveur d'application (Gunicorn)

Gunicorn est le serveur WSGI qui exécute l'application Django en production (on n'utilise jamais `runserver` en production, qui est réservé au développement).

Pour un test rapide, le projet fournit la recette :

```bash
just run_gunicorn
```

Pour un fonctionnement permanent (démarrage automatique, redémarrage en cas de plantage), gérez Gunicorn avec **systemd**. Créez `/etc/systemd/system/sites-conformes.service` :

```ini
[Unit]
Description=Gunicorn pour Sites Conformes
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/sites-conformes
EnvironmentFile=/opt/sites-conformes/.env
ExecStart=/opt/sites-conformes/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/opt/sites-conformes/gunicorn.sock \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

- `EnvironmentFile=/opt/sites-conformes/.env` indique à systemd de charger les variables d'environnement depuis le fichier `.env` créé à l'étape 3. C'est ainsi que Gunicorn récupère `SECRET_KEY`, `DATABASE_URL`, etc. Adaptez le chemin si vous avez installé l'application ailleurs.
- `config.wsgi:application` est le chemin vers le module WSGI ; adaptez `config` au nom réel du dossier de configuration du projet.
- Le `--bind unix:...sock` crée un socket *Unix* (un fichier) que Nginx utilisera pour parler à Gunicorn : plus rapide et plus sûr qu'un port réseau pour une communication locale.
- Règle empirique pour `--workers` : `(2 × nombre de cœurs CPU) + 1`.
- Avec `uv`, remplacez le chemin de l'`ExecStart` par `uv run gunicorn …` exécuté dans le répertoire du projet.

Activez et démarrez le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sites-conformes
sudo systemctl status sites-conformes
```

## Étape 5 — Configurer un reverse proxy (Nginx)

Nginx se place devant Gunicorn : il reçoit les requêtes des visiteurs, sert directement les fichiers statiques et médias, et transmet le reste à Gunicorn.

> 💡 Le projet fournit un script générateur de configuration Nginx, accessible via `just nginx-generate-config-file`. Vous pouvez l'utiliser comme point de départ plutôt que de tout écrire à la main.

Activez le site et rechargez Nginx :

```bash
sudo ln -s /etc/nginx/sites-available/sites-conformes /etc/nginx/sites-enabled/
sudo nginx -t          # vérifie la syntaxe de la configuration
sudo systemctl reload nginx
```

## Étape 6 — Indexation de la recherche

Les contenus des pages sont indexés pour permettre la recherche sur le site, par
la commande `update_index` (cf. la [documentation de Wagtail](https://docs.wagtail.org/en/stable/topics/search/indexing.html)).
Elle est déjà lancée par `just deploy` à chaque déploiement.

Il est recommandé d'y ajouter une **réindexation hebdomadaire**, pour corriger
d'éventuels écarts entre l'index et les contenus. Ajoutez une tâche cron :

```text
crontab -e
# Ajouter :
0 3 * * 0 /opt/sites-conformes/venv/bin/python /opt/sites-conformes/manage.py update_index
```

> Cette ligne lance `update_index` chaque dimanche à 3 h du matin (`0 3 * * 0` = minute 0, heure 3, tous les jours du mois, tous les mois, jour de semaine 0 = dimanche).

## Mise à jour (serveur Linux)

1. **Sauvegarder la base de données** :

```bash
pg_dump -U sites_conformes sites_conformes_db > sauvegarde_$(date +%F).sql
```

2. **Récupérer la dernière version du code et la branche `production`.**

3. **Mettre à jour les dépendances et réinitialiser le contenu généré** :
   - **Voie A (uv + just)** : `just update` (= `uv sync --no-group dev` puis `just deploy`, qui inclut migrations, fichiers statiques et indexation).
   - **Voie B (pip + venv)** :

     ```bash
     source venv/bin/activate
     pip install .
     python manage.py migrate
     python manage.py collectstatic --noinput --ignore="*.sass"
     ```

4. **Redémarrer le service** :

```bash
sudo systemctl restart sites-conformes
```

> 💡 **Ne pas confondre `just update` et `just upgrade`** : `update` met à jour l'application (synchronise les dépendances verrouillées et redéploie). `upgrade` **monte les versions** des dépendances (`uv lock --upgrade`, `pre-commit autoupdate`, `npm update`) : c'est une opération de maintenance du dépôt, à réserver au développement, pas à un serveur de production.

## Dans le cas d'un déploiement en RIE / réseau privé

Le Réseau Interministériel de l'État (RIE) est le réseau interne sécurisé reliant les administrations françaises. Le déploiement sur le RIE implique des contraintes réseau spécifiques.

### Contraintes principales [À FAIRE VÉRIFIER / RELIRE]

- **Pas d'accès direct à Internet** : tout le trafic sortant passe par des passerelles contrôlées. L'accès aux dépôts pip, npm, et aux registries Docker peut être bloqué.
- **Filtrage DNS** : seuls les domaines autorisés sont résolus.
- **Proxy HTTP obligatoire** : les requêtes sortantes doivent passer par le proxy du ministère.
- **Certificats spécifiques** : le RIE utilise ses propres autorités de certification. Les certificats Let's Encrypt ne sont pas utilisables.
- **Restrictions sur les ports** : seuls certains ports sont ouverts (typiquement 80, 443).

### Adaptations recommandées [À COMPLÉTER / FAIRE RELIRE PAR LES CONCERNÉ·ES]

- **Pas d'accès Internet sortant** : téléchargez les dépendances Python en amont depuis une machine connectée, puis transférez-les sur le serveur.
- **Accès au dépôt** : clonez le dépôt depuis une machine connectée puis transférez l'archive, ou configurez un miroir Git interne.
- **DNS interne** : nom de domaine résolu par le DNS interne à l'administration.
- **Proxy sortant** : si un proxy HTTP est nécessaire, configurez les variables `HTTP_PROXY` et `HTTPS_PROXY` dans l'environnement.
- **Certificats** : installez l'autorité de certification interne dans le magasin de certificats du système.
