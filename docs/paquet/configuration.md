# Configuration

Ce guide couvre uniquement les réglages spécifiques à `sites_conformes`. Pour
la configuration générale Wagtail/Django, référez-vous à leurs documentations
officielles.

La plupart des réglages se lisent depuis l’environnement, ce qui permet de
les modifier sans toucher au code. Les valeurs par défaut indiquées ci-dessous
sont celles utilisées dans le `config/settings.py` fourni en exemple par le
package.

:::{seealso}
Pour la **liste exhaustive** de toutes les variables d’environnement lues
par l’application (au-delà de celles spécifiques à l’intégration), voir la
{doc}`référence des variables d’environnement <../deploiement/variables-environnement>`.
:::

## HOST_URL

Hôte de votre site (sans protocole). Sert à construire les URL absolues.

```python
HOST_URL = os.getenv("HOST_URL", "localhost")
```

## HOST_PROTO

Protocole utilisé (`http` ou `https`). Par défaut **`https`**.

```python
HOST_PROTO = os.getenv("HOST_PROTO", "https")
```

## HOST_PORT

Port HTTP utilisé pour les URL générées (laissez vide en production).

```python
HOST_PORT = os.getenv("HOST_PORT", "")
```

## FORCE_SCRIPT_NAME

Préfixe d’URL si le site est servi depuis un sous-chemin (`/site-conformes/`,
par exemple). Voir [la doc Django](https://docs.djangoproject.com/en/stable/ref/settings/#force-script-name).

```python
FORCE_SCRIPT_NAME = os.getenv("FORCE_SCRIPT_NAME", "").rstrip("/")
```

## WAGTAILADMIN_PATH

Chemin d’accès à l’administration Wagtail. Par défaut **`cms-admin/`**, pour
éviter la collision avec `/admin/` (souvent réservé à Django admin).

```python
WAGTAILADMIN_PATH = os.getenv("WAGTAILADMIN_PATH", "cms-admin/")
```

## WAGTAIL_I18N_ENABLED

Active l’internationalisation de Wagtail :

```python
WAGTAIL_I18N_ENABLED = True
```

## PROCONNECT_ACTIVATED

Active l’authentification ProConnect (réservée aux agents de l’État). Lue
depuis l’environnement, désactivée par défaut.

```python
PROCONNECT_ACTIVATED = os.getenv("PROCONNECT_ACTIVATED", "") in ("1", "True")
```

Quand `True`, le package ajoute automatiquement `sites_conformes.proconnect`
à `INSTALLED_APPS` et configure le backend OIDC (voir
{doc}`installation`).

## SF_USE_DB_STORAGE

Stocke les fichiers médias en base de données plutôt que sur le filesystem.
Utile pour les PaaS avec filesystem éphémère (Scalingo, Heroku). Non
recommandé au-delà de ~1 Go de médias : privilégiez S3.

```python
SF_USE_DB_STORAGE = getenv_bool("SF_USE_DB_STORAGE", False)
```

Quand `True`, `sites_conformes.db_storage` doit être ajouté à
`INSTALLED_APPS` (voir {doc}`installation`).

## SF_USE_WHITENOISE

Active WhiteNoise pour servir les fichiers statiques sans serveur de fichiers
dédié. Désactivé par défaut.

```python
SF_USE_WHITENOISE = getenv_bool("SF_USE_WHITENOISE", False)
```

## SF_DISABLE_LOCAL_LOGIN

Désactive la connexion par identifiant et mot de passe : seul ProConnect permet
alors de se connecter. Désactivé par défaut.

```python
SF_DISABLE_LOCAL_LOGIN = getenv_bool("SF_DISABLE_LOCAL_LOGIN", False)
```

Le réglage n’a d’effet que si `PROCONNECT_ACTIVATED` vaut aussi `True` : la
connexion par mot de passe ne peut pas être désactivée sans autre moyen de se
connecter. Sans ProConnect, le formulaire de connexion reste affiché.

:::{warning}
Côté package, ce réglage ne fait que **masquer** le formulaire de connexion.
La vue de connexion accepte toujours un identifiant et un mot de passe tant
que `django.contrib.auth.backends.ModelBackend` figure dans
`AUTHENTICATION_BACKENDS`. Il faut donc le retirer dans les réglages du projet
hôte :

```python
if PROCONNECT_ACTIVATED:
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

Le backend ProConnect hérite de `ModelBackend` : les droits des utilisateurs
continuent de fonctionner. La réinitialisation et le changement de mot de
passe sont désactivés, et les formulaires de création et de modification
d’utilisateur n’ont plus de champ mot de passe : un compte créé dans l’admin
ne sert qu’à autoriser à l’avance une connexion via ProConnect (le compte est
retrouvé par son adresse e-mail). Les sessions déjà ouvertes par mot de passe
sont fermées au prochain chargement de page.
:::

:::{seealso}
Pour les réglages Django et Wagtail, référez-vous à leurs documentations
officielles : <https://docs.djangoproject.com/> et <https://docs.wagtail.org/>.
:::
