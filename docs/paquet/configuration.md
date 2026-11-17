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

Pour ajouter un appareil de double authentification (2FA), un code envoyé par
e-mail remplace alors la saisie du mot de passe : l’envoi d’e-mails doit être
configuré (`DEFAULT_FROM_EMAIL`), sinon l’ajout d’un appareil est bloqué. Voir
{doc}`../fonctionnalites/2fa`.

(acces-de-secours)=

### Accès de secours

Si ProConnect est indisponible, ou si plus aucun compte n’a les droits
nécessaires, une personne ayant accès au serveur peut rétablir
temporairement la connexion par mot de passe :

1. Passer `SF_DISABLE_LOCAL_LOGIN` à `False` et redémarrer l’application : le
   formulaire de connexion réapparaît à côté du bouton ProConnect.
2. Définir un mot de passe pour un compte superadmin avec
   `python manage.py changepassword <identifiant>`, ou créer un compte avec
   `python manage.py createsuperuser`. Les comptes créés dans l’admin ont un
   mot de passe vide, et ceux créés via ProConnect un mot de passe inconnu.
   Pour lancer ces commandes selon l’hébergement, voir
   {doc}`../deploiement/scalingo`, {doc}`../deploiement/docker` ou
   {doc}`../deploiement/serveur-linux`.
3. Se connecter et faire l’opération nécessaire, par exemple donner des droits
   à un compte ProConnect.
4. Remettre `SF_DISABLE_LOCAL_LOGIN` à `True` et redémarrer : les sessions
   ouvertes par mot de passe sont fermées.

Si la 2FA est activée, le code de l’appareil est demandé après la connexion. Si
le compte n’a pas encore d’appareil, l’ajout est à confirme avec le mot de passe
défini ci-dessus.

:::{warning}
Pendant cette opération, la connexion par mot de passe est rétablie pour **tous**
les comptes qui en ont un.
:::

:::{seealso}
Pour les réglages Django et Wagtail, référez-vous à leurs documentations
officielles : <https://docs.djangoproject.com/> et <https://docs.wagtail.org/>.
:::
