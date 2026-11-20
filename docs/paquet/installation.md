# Ajouter Sites Conformes à un projet Django existant

Vous avez déjà un projet Django, avec ses propres réglages, URL et base de
données ? Vous pouvez y installer Sites Conformes comme un paquet Python.

Résultat : votre projet sert à la fois vos vues existantes et des pages
éditoriales au format DSFR, publiées par vos rédacteurs depuis un back-office.

Sites Conformes s’installe comme une dépendance, puis vous déclarez ses
applications, ses gabarits et ses URL dans votre projet. Rien n’est modifié
dans votre code existant : les tables du paquet s’ajoutent simplement aux
vôtres dans la même base de données.

:::{tip}
Pour un nouveau projet, `bouture` écrit toute cette configuration à votre
place : voir {doc}`nouveau-projet`. Générer un projet à côté du vôtre est
aussi un bon moyen de comparer les réglages.
:::

:::{note}
**Votre projet n’utilise pas encore Wagtail ?** Sites Conformes est construit
sur [Wagtail](https://wagtail.org/), le gestionnaire de contenu qui fournit
le back-office. Commencez par
[l’intégrer à votre projet Django](https://docs.wagtail.org/en/stable/getting_started/integrating_into_django.html)
(applications `wagtail.*`, intergiciels, URL de l’administration). Les
réglages de cette page viennent ensuite.
:::

## Prérequis

- Python 3.12 ou supérieur (testé sur 3.12, 3.13, 3.14)
- Django 6.0 ou supérieur
- Wagtail 7.2 ou supérieur
- PostgreSQL (recommandé en production) ou SQLite

## Installation avec uv

```sh
uv add sites-conformes
```

(Si vous utilisez encore `pip` : `pip install sites-conformes`.)

## Configuration

Ajoutez la configuration suivante à votre fichier de réglages.

### Lecture des variables d’environnement

Plusieurs réglages du paquet se lisent dans l’environnement. Définissez cette
petite fonction en haut de votre fichier de réglages :

```python
import os
from pathlib import Path


def getenv_bool(key: str, default: bool) -> bool:
    try:
        value = os.environ[key]
    except KeyError:
        return default
    return value.casefold() in ("1", "true")


SF_USE_DB_STORAGE = getenv_bool("SF_USE_DB_STORAGE", False)
SF_USE_WHITENOISE = getenv_bool("SF_USE_WHITENOISE", False)
PROCONNECT_ACTIVATED = os.getenv("PROCONNECT_ACTIVATED", "") in ("1", "True")
SF_DISABLE_LOCAL_LOGIN = getenv_bool("SF_DISABLE_LOCAL_LOGIN", False)
```

### INSTALLED_APPS

```python
INSTALLED_APPS.extend([
    "dsfr",
    # Le package lui-même (fournit les templates de base partagés)
    "sites_conformes",
    # Les apps qu’il contient
    "sites_conformes.customimages",
    "sites_conformes.core",
    "sites_conformes.blog",
    "sites_conformes.events",
    "sites_conformes.forms",
    "sites_conformes.menus",
    "sites_conformes.dashboard",
    # Dépendances Wagtail/tierces requises
    "wagtail.contrib.settings",
    "wagtail.contrib.typed_table_block",
    "wagtail.contrib.routable_page",
    "wagtailmenus",
    "wagtailmarkdown",
    "wagtail_honeypot",
])

# Stockage des médias en base de données (Scalingo, Heroku, etc.)
if SF_USE_DB_STORAGE:
    INSTALLED_APPS.append("sites_conformes.db_storage")

# Authentification ProConnect (DGFiP/DINUM)
if PROCONNECT_ACTIVATED:
    INSTALLED_APPS += [
        "mozilla_django_oidc",
        "sites_conformes.proconnect",
    ]
    # Avec SF_DISABLE_LOCAL_LOGIN, on retire ModelBackend pour que la connexion
    # par mot de passe soit réellement impossible (masquer le formulaire ne suffit pas)
    if SF_DISABLE_LOCAL_LOGIN:
        AUTHENTICATION_BACKENDS = []
        WAGTAIL_PASSWORD_RESET_ENABLED = False
        WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
        WAGTAILUSERS_PASSWORD_ENABLED = False
    else:
        AUTHENTICATION_BACKENDS = [
            "django.contrib.auth.backends.ModelBackend",
        ]

    AUTHENTICATION_BACKENDS.append("sites_conformes.proconnect.backends.OIDCAuthenticationBackend")
```

### Processeurs de contexte

```python
TEMPLATES[0]["OPTIONS"]["context_processors"].extend([
    "wagtail.contrib.settings.context_processors.settings",
    "wagtailmenus.context_processors.wagtailmenus",
    "sites_conformes.core.context_processors.skiplinks",
])
```

Sans `wagtail.contrib.settings.context_processors.settings`, l’en-tête et le
pied de page restent vides (sans erreur) : ils y lisent le titre du site, le
logo et les intitulés.

### Gabarits et fichiers statiques

Le paquet fournit des gabarits de base partagés (`base.html`, blocs DSFR,
menus) et des fichiers statiques. Pour que le chargeur `filesystem` les
trouve, ajoutez les chemins suivants :

```python
import sites_conformes

PACKAGE_DIR = Path(sites_conformes.__file__).resolve().parent

TEMPLATES[0]["DIRS"].append(PACKAGE_DIR / "templates")
STATICFILES_DIRS = (PACKAGE_DIR / "static",) + tuple(STATICFILES_DIRS)
```

(`APP_DIRS = True` couvre déjà les gabarits propres à chaque application, par
exemple `sites_conformes/blog/templates/`. Les ajouts ci-dessus servent
uniquement aux gabarits placés au niveau du paquet.)

### Réglages divers

```python
# Chemin d’accès à l’admin Wagtail. Par défaut côté package : "cms-admin/".
WAGTAILADMIN_PATH = os.getenv("WAGTAILADMIN_PATH", "cms-admin/")

# Hôte et protocole utilisés pour générer les URL absolues.
HOST_URL = os.getenv("HOST_URL", "localhost")
HOST_PROTO = os.getenv("HOST_PROTO", "https")

WAGTAIL_I18N_ENABLED = True

# Modèle d’image fourni par le package (texte alternatif non prérempli
# avec le titre de l’image). Obligatoire : les migrations du package en dépendent.
WAGTAILIMAGES_IMAGE_MODEL = "sites_conformes_customimages.CustomImage"
```

Voir {doc}`configuration` pour la liste complète des réglages disponibles.

## URL

`sites_conformes.core.urls` sert les pages publiées dans le back-office, à
l’adresse choisie par les rédacteurs. Il répond donc à **toutes** les URL non
reconnues avant lui : incluez-le **en dernier**, sinon une URL déclarée après
lui ne serait jamais atteinte.

```python
# config/urls.py
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.urls import include, path
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

urlpatterns = [
    # … vos URL existantes
    path(settings.WAGTAILADMIN_PATH, include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
]

urlpatterns += i18n_patterns(
    path("", include("sites_conformes.core.urls")),
    prefix_default_language=False,
)
```

Conséquence : si votre projet sert déjà une page à la racine, c’est elle qui
s’affiche, pas la page d’accueil créée dans le back-office.

`i18n_patterns` sert le site en plusieurs langues. Avec
`prefix_default_language=False`, les adresses en français n’ont pas de
préfixe `/fr/`.

### Pages d’erreur

Le paquet fournit des pages d’erreur au format DSFR (403, 404, 500). Django ne
les active pas tout seul — il ne connaît que `404.html` et `500.html` placés à
la racine. Déclarez donc celles du paquet dans votre fichier d’URL :

```python
from functools import partial

from django.views.defaults import page_not_found, permission_denied, server_error

handler403 = partial(permission_denied, template_name="sites_conformes_core/403.html")
handler404 = partial(page_not_found, template_name="sites_conformes_core/404.html")
handler500 = partial(server_error, template_name="sites_conformes_core/500.html")
```

## Modèle de page

Facultatif : si vos pages de contenu ont besoin de champs ou de blocs à vous.
Vous pouvez alors remplacer le modèle de page de contenu par le vôtre — de
préférence **avant** les premières migrations du paquet, tant qu’aucune page
n’existe. Voir {doc}`modele-de-page-personnalise`.

## Migrations et collecte des fichiers statiques

```sh
python manage.py migrate
python manage.py collectstatic
python manage.py create_starter_pages
```

`migrate` ajoute les tables du paquet à votre base, sans toucher aux vôtres.
`collectstatic` rassemble ses fichiers statiques (feuilles de style,
pictogrammes) avec ceux de votre projet. `create_starter_pages` est
facultatif : il crée l’accueil, les mentions légales, la déclaration
d’accessibilité et une page de contact — lancez-le **après** `collectstatic`,
dont il lit les pictogrammes.

Le back-office est alors sur `WAGTAILADMIN_PATH` (`/cms-admin/` par défaut).

## Prochaines étapes

- {doc}`configuration` : réglages spécifiques
- {doc}`modele-de-page-personnalise` : ajouter des champs aux pages de contenu
- {doc}`exemple-annuaire` : afficher une donnée métier dans une page
