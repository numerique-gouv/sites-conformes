# Installation

Ce guide explique comment ajouter `sites-conformes` à un projet Django existant.

## Prérequis

- Python 3.12 ou supérieur (testé sur 3.12, 3.13, 3.14)
- Django 6.0 ou supérieur
- Wagtail 7.2 ou supérieur
- PostgreSQL

## Installation via uv

```bash
uv add sites-conformes
```

(Si vous utilisez encore `pip` : `pip install sites-conformes`.)

## Configuration

Ajoutez la configuration suivante à votre `config/settings.py`.

### Lecture des variables d'environnement

Plusieurs réglages du package sont pilotés par des variables d'environnement.
Définissez un petit helper en haut de votre `settings.py` :

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
```

### INSTALLED_APPS

```python
INSTALLED_APPS.extend([
    "dsfr",
    # Le package lui-même (fournit les templates de base partagés)
    "sites_conformes",
    # Les apps qu'il contient
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
    "wagtail_modeladmin",
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
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
        "sites_conformes.proconnect.backends.OIDCAuthenticationBackend",
    ]
```

### Context processors

```python
TEMPLATES[0]["OPTIONS"]["context_processors"].extend([
    "wagtailmenus.context_processors.wagtailmenus",
    "sites_conformes.core.context_processors.skiplinks",
    "sites_conformes.core.context_processors.mega_menus",
])
```

### Templates et fichiers statiques

Le package fournit des templates de base partagés (`base.html`, blocs DSFR,
menus) et des assets statiques. Pour que Django les trouve via le loader
filesystem, ajoutez les chemins suivants :

```python
import sites_conformes

PACKAGE_DIR = Path(sites_conformes.__file__).resolve().parent

TEMPLATES[0]["DIRS"].append(PACKAGE_DIR / "templates")
STATICFILES_DIRS = (PACKAGE_DIR / "static",) + tuple(STATICFILES_DIRS)
```

(`APP_DIRS = True` couvre déjà les templates spécifiques à chaque app, par
exemple `sites_conformes/blog/templates/`. Les ajouts ci-dessus servent
uniquement aux templates au niveau du package.)

### Réglages divers

```python
# Chemin d'accès à l'admin Wagtail. Par défaut côté package : "cms-admin/".
WAGTAILADMIN_PATH = os.getenv("WAGTAILADMIN_PATH", "cms-admin/")

# Hôte et protocole utilisés pour générer les URL absolues.
HOST_URL = os.getenv("HOST_URL", "localhost")
HOST_PROTO = os.getenv("HOST_PROTO", "https")

WAGTAIL_I18N_ENABLED = True
```

Voir {doc}`configuration` pour la liste complète des réglages disponibles.

## Migrations et collecte des fichiers statiques

```bash
python manage.py migrate
python manage.py collectstatic
```

## Prochaines étapes

- {doc}`configuration` : réglages spécifiques
