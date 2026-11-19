# Créer un nouveau projet

Vous démarrez de zéro, et vous avez du code métier à mettre à côté du site :
des modèles, une API, des vues sur mesure ? Cette page vous génère un projet
prêt à lancer, dans lequel vous ajoutez ensuite votre code.

Au bout des étapes ci-dessous, vous avez un site qui tourne sur votre poste,
avec son back-office.

:::{note}
Si vous n’avez aucun développement à ajouter, cette page n’est pas la bonne :
déployez plutôt une instance à partir du dépôt, voir
{doc}`../deploiement/index`.
:::

## Le principe

Sites Conformes s’installe comme une dépendance Python de votre projet, au
même titre que Django ou Wagtail. Votre projet, lui, ne contient que ce qui
vous est propre : les réglages, les URL et vos applications.

Écrire ces réglages à la main est long : le paquet s’appuie sur une
trentaine d’applications Django et Wagtail à déclarer dans le bon ordre.
[`bouture`](https://github.com/treto-dev/bouture) le fait pour vous et génère
un projet minimal, comme `wagtail start` le fait pour un site Wagtail.

## Prérequis

- Python 3.12 ou supérieur
- [`uv`](https://docs.astral.sh/uv/)

:::{tip}
**C’est quoi `uv` ?** Un gestionnaire de paquets et d’environnements Python,
un remplaçant rapide de `pip` et `venv`. Deux commandes reviennent dans cette
page :

- `uvx <outil>` télécharge un outil et le lance, sans l’installer ;
- `uv run <commande>` lance une commande dans l’environnement du projet,
  après avoir installé ses dépendances si besoin.
:::

## Étape 1 — Créer le projet

```sh
uvx bouture start monsite
```

`monsite` est le nom du projet : la commande crée un dossier de ce nom.

Elle pose ensuite quelques questions. Seuls les réglages des fonctionnalités
que vous choisissez sont écrits dans le fichier de réglages, ce qui le garde
court :

| Question | Ce que vous choisissez |
| --- | --- |
| Titre, sous-titre, intitulé officiel | Les textes affichés dans l’en-tête du site, à côté de la Marianne |
| Base de données | SQLite (rien à installer) ou PostgreSQL |
| Stockage des images et documents | Fichiers locaux (développement seulement), base de données ou bucket S3 |
| ProConnect | Connexion au back-office via ProConnect, en plus du mot de passe |
| Authentification à deux facteurs | L’imposer pour les comptes du back-office |
| Sentry | Le suivi des erreurs |
| Langues | Les langues du site en plus du français |

Aucune réponse n’est définitive : tout se retrouve en clair dans
`config/settings.py`, modifiable ensuite. Pour les options de stockage, voir
{doc}`../donnees/stockage-medias`.

Pour ne répondre à aucune question, l’option `--no-input` crée le projet le
plus simple : SQLite, fichiers locaux, aucune de ces fonctionnalités.

### Ce que contient le projet

```text
monsite/
├── config/
│   ├── settings.py   # réglages, à modifier librement
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── pyproject.toml    # dépend de sites-conformes
├── config.json       # titre et intitulés, lus à la création des pages
├── .env              # SECRET_KEY, DEBUG et variables des fonctionnalités choisies
└── README.md
```

C’est un projet Django ordinaire : le code de Sites Conformes n’y est pas. Il
est installé à part, par `uv`, à partir du `pyproject.toml` (version 4.4
minimum demandée).

Le `.env` contient les valeurs propres à votre poste, dont la clé secrète de
Django. Ne le versionnez pas : le `.gitignore` généré l’exclut déjà.

## Étape 2 — Choisir le modèle de page (facultatif)

Seulement si vos **pages de contenu** ont besoin de champs ou de blocs à vous
: un sous-titre, une date de mise à jour, une FAQ…

Vous pouvez remplacer le modèle de page de contenu de Sites Conformes par le
vôtre, de préférence **maintenant**, avant la première migration : tant
qu’aucune page n’existe, ça ne coûte rien.

Créez d’abord une application pour accueillir ce modèle :

```sh
cd monsite
uv run python manage.py startapp pages
```

Puis suivez {doc}`modele-de-page-personnalise`, en préfixant ses commandes
par `uv run`.

Pas sûr d’en avoir besoin ? Passez votre tour : on peut changer de modèle
plus tard avec `bern`, voir {ref}`changer-de-modele-site-existant`.

## Étape 3 — Lancer le site

```sh
cd monsite
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
uv run python manage.py create_starter_pages
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

`migrate` crée les tables de la base de données, `collectstatic` rassemble
les fichiers statiques (feuilles de style, pictogrammes) dans `staticfiles/`,
`create_starter_pages` crée les premières pages (accueil, mentions légales,
déclaration d’accessibilité, contact), `createsuperuser` votre compte
d’administration, et `runserver` lance le serveur de développement.

:::{note}
Lancez `create_starter_pages` **après** `collectstatic` : elle lit les
pictogrammes dans les fichiers que `collectstatic` a rassemblés.
:::

Le site répond alors sur <http://localhost:8000/>, le back-office sur
<http://localhost:8000/cms-admin/>.

## Étape 4 — Ajouter votre donnée métier

Vos applications vivent à côté de celles du paquet : vous mettez Sites
Conformes à jour sans toucher à votre code, et inversement.

Créez une application, ici pour un annuaire :

```sh
uv run python manage.py startapp annuaire
```

Puis :

1. Ajoutez `"annuaire"` à `INSTALLED_APPS`, dans `config/settings.py`.
2. Déclarez vos modèles, blocs et vues comme dans n’importe quel projet
   Django.
3. Ajoutez vos URL dans `config/urls.py`, **avant** l’inclusion de
   `sites_conformes.core.urls`.

L’ordre compte : `sites_conformes.core.urls` sert les pages publiées dans le
back-office, à n’importe quelle adresse. Il répond donc à toutes les URL
qui n’ont pas été reconnues avant lui — une URL déclarée après ne serait
jamais atteinte.

{doc}`exemple-annuaire` montre un exemple complet : un modèle métier éditable
dans le back-office, affiché dans une page.

## Personnaliser l’apparence

Les pages s’affichent à partir des gabarits fournis par le paquet. Pour en
surcharger un, créez dans votre projet un gabarit **au même chemin** : il
passe alors avant.

Créez un dossier `templates/` à côté de `manage.py`. Pour remplacer
l’en-tête du site, par exemple, créez le fichier
`templates/sites_conformes_core/blocks/header.html`.

:::{warning}
Un gabarit que vous surchargez ne reçoit plus les corrections du paquet :
surchargez-en le moins possible, et comparez-les à ceux du paquet à chaque
mise à jour.
:::

## Mettre à jour Sites Conformes

Pour passer à une nouvelle version :

```sh
uv lock --upgrade-package sites-conformes
uv run python manage.py migrate
```

Consultez le {doc}`../changelog` à chaque mise à jour : il indique les actions
manuelles requises.

Si vous avez remplacé le modèle de page, générez aussi les migrations de
votre application : voir {doc}`modele-de-page-personnalise`.

## Voir aussi

- {doc}`configuration` : les réglages propres à Sites Conformes.
- {doc}`../deploiement/variables-environnement` : les variables
  d’environnement lues par l’application.
- Pour la mise en production, votre projet se déploie comme n’importe quel
  projet Django. Les pages de {doc}`../deploiement/index` décrivent le
  déploiement du dépôt, mais leurs conseils sur le serveur, la base de
  données et le stockage des médias s’appliquent aussi à vous.
