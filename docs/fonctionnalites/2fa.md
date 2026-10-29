# Authentification à deux facteurs (2FA)

## Contexte

L’ANSSI [recommande](https://messervices.cyber.gouv.fr/guides/recommandations-relatives-lauthentification-multifacteur-et-aux-mots-de-passe)
la mise en place d’une authentification à deux facteurs (2FA) pour sécuriser
l’accès des comptes privilégiés (en l’occurrence, l’accès à l’interface
d’administration Wagtail)

Sites Conformes intègre [wagtail-2fa](https://github.com/labd/wagtail-2fa)
pour mettre en place un système de mot de passe à usage unique basé sur le temps
(Time based One Time Password ou TOTP.) Cette méthode de 2FA repose sur une
application tierce installée sur le téléphone de l’utilisateur, qui génère un
code à 6 chiffres renouvelé toutes les 30 secondes.
Lors de la connexion, ce code est exigé en complément du mot de passe.

## Activation

Par défaut, la 2FA est **optionnelle** sur Sites Conformes : les utilisateurs
peuvent la configurer, mais elle n’est pas obligatoire.
Pour la rendre obligatoire pour tous les accès à l’interface d’administration :

```python
WAGTAIL_2FA_REQUIRED=True
```

Avec cette option, tout utilisateur authentifié sans appareil 2FA configuré est
automatiquement redirigé vers la page de configuration avant de pouvoir accéder
à l’interface d’administration.

## Fonctionnement

### Pour l’utilisateur

1. À la première connexion (ou si la 2FA est obligatoire), l’utilisateur est
redirigé vers `/cms-admin/2fa/devices/new`.
2. Il scanne le QR code avec une application compatible (Google Authenticator,
Aegis, Authy, 1Password…).
3. Il saisit un code de vérification pour confirmer la configuration.
4. Lors des connexions suivantes, un écran intermédiaire lui demande son code à
6 chiffres.

## Connexion via ProConnect

ProConnect sait réaliser lui-même une double authentification. Pour éviter de
redemander un code 2FA local après une connexion ProConnect :

```python
PROCONNECT_DELEGATE_2FA=True
```

Avec cette option :

- ProConnect est tenu d’exiger une double authentification à chaque connexion
(niveaux `eidas0-mfa`, `eidas1-mfa`, `eidas2` ou `eidas3`) ;
- le niveau renvoyé par ProConnect (claim `acr` de l’ID token) est toujours
vérifié : si la double authentification n’est pas confirmée, le code 2FA local
reste demandé ;
- une connexion par identifiant et mot de passe demande toujours le code 2FA
local ;
- un utilisateur connecté via ProConnect n’a pas besoin de configurer d’appareil
2FA local, même si `WAGTAIL_2FA_REQUIRED=True`.

Voir la [documentation ProConnect](https://partenaires.proconnect.gouv.fr/docs/fournisseur-service/double_authentification).

## Accéder à la gestion des appareils 2FA

Le lien vers la page de gestion des appareils 2FA est accessible depuis :

- **Liste des utilisateurs** : `/cms-admin/users/` → bouton **"Gérer 2FA"**
sur chaque ligne (réservé aux administrateurs)
- **Page de compte** : cliquer sur son avatar/nom en bas à gauche →
"Paramètres du compte" → onglet **"Plus d’actions"** (onglet visible uniquement
si des actions sont disponibles) → "Manage your 2FA devices"

## Middleware et fichiers statiques

Lorsque `WAGTAIL_2FA_REQUIRED=True`, le middleware `VerifyUserMiddleware`
intercepte toutes les requêtes entrantes pour les utilisateurs non vérifiés.
Cela inclut les requêtes vers les fichiers statiques (CSS, JS),
ce qui empêche le navigateur de les charger.

Sites Conformes fournit une sous-classe du middleware qui exclut les URLs
statiques et médias de cette vérification.

Elle remplace `wagtail_2fa.middleware.VerifyUserMiddleware` dans `MIDDLEWARE` :

```python
# config/settings.py
MIDDLEWARE = [
    ...
    "sites_conformes.dashboard.middleware.VerifyUserStaticFilesMiddleware",
    ...
]
```
