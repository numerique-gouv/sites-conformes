# Référence des variables d'environnement

Ce tableau recense **toutes** les variables d'environnement lues par l'application (fichier `config/settings.py`). Il complète le [`.env.example`](https://github.com/numerique-gouv/sites-conformes/blob/main/.env.example) du dépôt, qui reste la source de vérité en cas d'évolution. La plupart ont une valeur par défaut : vous ne renseignez que celles dont vous avez besoin.

> 📦 Si vous intégrez Sites Conformes comme **paquet** dans un projet Django existant, la façon de câbler ces réglages dans votre `settings.py` est décrite dans {doc}`../paquet/configuration`.

Niveaux : 🔴 indispensable · 🟠 recommandé selon l'usage · ⚪ optionnel / avancé.

## Modèle minimal à copier

Les variables ci-dessous sont les **strictement indispensables** : sans elles, le
site ne démarre pas. Copiez ce bloc (bouton en haut à droite), collez-le dans
votre `.env` et remplacez les valeurs.

```bash
# --- Réglages indispensables ---
SECRET_KEY=            # à générer aléatoirement (voir la page Scalingo, étape 4)
DEBUG=False            # toujours False en production
ALLOWED_HOSTS=mon-domaine.gouv.fr
HOST_URL=mon-domaine.gouv.fr
DATABASE_URL=          # rempli automatiquement sur Scalingo
```

Pour un site complet (e-mails, images), ajoutez ensuite les réglages 🟠 des
sections ci-dessous. Le [`.env.example`](https://github.com/numerique-gouv/sites-conformes/blob/main/.env.example)
du dépôt fournit un modèle complet et commenté.

## Général et sécurité

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `SECRET_KEY` | Clé secrète de signature (sessions, mots de passe). À générer aléatoirement. | *(aucun)* | 🔴 |
| `DEBUG` | Mode débogage. **Toujours `False` en production.** | `False` | 🔴 |
| `ALLOWED_HOSTS` | Domaines autorisés à servir le site, séparés par des virgules. | `127.0.0.1,.localhost` | 🔴 |
| `DATABASE_URL` | Adresse de connexion à la base PostgreSQL. Rempli automatiquement sur Scalingo. | *(aucun, obligatoire)* | 🔴 |
| `AUTH_PASSWORD_MINIMUM_LENGTH` | Longueur minimale des mots de passe des comptes. | `15` | ⚪ |

## Domaine et URL

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `HOST_URL` | Nom de domaine principal du site (sans `https://`). | `localhost` | 🔴 |
| `HOST_PROTO` | Protocole utilisé (`http` ou `https`). | `https` | 🟠 |
| `HOST_PORT` | Port, si différent du port standard. | *(vide)* | ⚪ |
| `WAGTAILADMIN_BASE_URL` | URL de base insérée dans les e-mails (liens de réinitialisation, notifications). Si vide, reconstruite à partir de `HOST_PROTO` + `HOST_URL`. | *(reconstruit)* | 🟠 |
| `CSRF_TRUSTED_ORIGINS` | Origines de confiance pour les formulaires, séparées par des virgules. Si vide, déduites de `ALLOWED_HOSTS`. | *(déduit)* | ⚪ |
| `USE_X_FORWARDED_HOST` | À activer si un proxy place le vrai domaine dans l'en-tête `X-Forwarded-Host`. | `False` | ⚪ |
| `FORCE_SCRIPT_NAME` | Préfixe d'URL si le site est servi sous un sous-chemin (ex. `/mon-site`). | *(vide)* | ⚪ |

## Stockage des fichiers (statiques et médias)

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `MEDIA_ROOT` | Dossier local de stockage des médias (mode fichier). | *(racine du projet)* | 🟠 |
| `MEDIA_URL` | Préfixe d'URL des médias. | `medias/` (ou `db-storage/`) | ⚪ |
| `STATIC_URL` | Préfixe d'URL des fichiers statiques. | `static/` | ⚪ |
| `SF_USE_WHITENOISE` | Sert les fichiers statiques via WhiteNoise (pratique sans serveur web dédié). | `False` | 🟠 |
| `SF_PROD_SERVE_STATIC` | Autorise Django à servir les statiques même en production. | `False` | ⚪ |
| `SF_USE_DB_STORAGE` | Stocke les médias dans la base PostgreSQL (utile sur PaaS sans disque ; déconseillé au-delà d'1 Go). Voir {doc}`../donnees/stockage-medias`. | `False` | 🟠 |

## Stockage objet S3

> Le stockage S3 s'active dès que `S3_HOST` est renseigné ; il a alors la priorité sur les autres modes de stockage.

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `S3_HOST` | Adresse du service S3 (sans `https://`). Sa présence active le mode S3. | *(vide)* | 🟠 |
| `S3_BUCKET_NAME` | Nom du bucket (espace de stockage). | `set-bucket-name` | 🟠 |
| `S3_BUCKET_REGION` | Région du bucket. | `fr` | 🟠 |
| `S3_KEY_ID` | Identifiant d'accès. | `123` | 🟠 |
| `S3_KEY_SECRET` | Clé secrète d'accès. | `secret` | 🟠 |
| `S3_LOCATION` | Sous-dossier dans le bucket (permet de partager un bucket entre plusieurs sites). | *(vide)* | ⚪ |
| `S3_PROTOCOL` | Protocole de connexion au service S3. | `https` | ⚪ |
| `S3_PUBLIC_HOST` | Hôte public distinct de l'hôte interne (cas d'un MinIO derrière un proxy). | *(vide)* | ⚪ |

## Envoi d'e-mails

> L'envoi d'e-mails ne s'active que si `DEFAULT_FROM_EMAIL` est renseigné.

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `DEFAULT_FROM_EMAIL` | Adresse d'expéditeur. Sa présence active la configuration e-mail. | *(vide)* | 🟠 |
| `EMAIL_BACKEND` | Moteur d'envoi d'e-mails. | `smtp.EmailBackend` | ⚪ |
| `EMAIL_HOST` | Serveur SMTP d'envoi. | *(aucun)* | 🟠 |
| `EMAIL_PORT` | Port du serveur SMTP. | *(aucun)* | 🟠 |
| `EMAIL_HOST_USER` | Identifiant SMTP. | *(aucun)* | 🟠 |
| `EMAIL_HOST_PASSWORD` | Mot de passe SMTP. | *(aucun)* | 🟠 |
| `EMAIL_USE_TLS` | Connexion sécurisée TLS. | *(aucun)* | 🟠 |
| `EMAIL_USE_SSL` | Connexion sécurisée SSL implicite. | *(aucun)* | ⚪ |
| `EMAIL_TIMEOUT` | Délai d'expiration en secondes. | `30` | ⚪ |
| `EMAIL_SSL_KEYFILE` | Fichier de clé PEM (si TLS/SSL). | *(aucun)* | ⚪ |
| `EMAIL_SSL_CERTFILE` | Fichier de certificat PEM (si TLS/SSL). | *(aucun)* | ⚪ |
| `WAGTAIL_PASSWORD_RESET_ENABLED` | Affiche le lien « mot de passe oublié ». | `False` | 🟠 |

## Connexion ProConnect (authentification de l'État)

> Tout ce bloc n'est lu que si `PROCONNECT_ACTIVATED` vaut `True`. `CLIENT_ID` et `CLIENT_SECRET` sont alors indispensables.

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `PROCONNECT_ACTIVATED` | Active la connexion via ProConnect. | `False` | 🟠 |
| `PROCONNECT_CLIENT_ID` | Identifiant client fourni par ProConnect. | *(vide)* | 🔴 (si activé) |
| `PROCONNECT_CLIENT_SECRET` | Secret client fourni par ProConnect. | *(vide)* | 🔴 (si activé) |
| `PROCONNECT_CREATE_USER` | Crée automatiquement le compte à la première connexion. | `True` | ⚪ |
| `PROCONNECT_SCOPES` | Périmètre des informations demandées. | `openid given_name usual_name email siret uid` | ⚪ |
| `PROCONNECT_SIGN_ALGO` | Algorithme de signature. | `RS256` | ⚪ |
| `PROCONNECT_DOMAIN` | Domaine du fournisseur ProConnect. | `fca.integ01.dev-agentconnect.fr` | 🟠 |
| `PROCONNECT_API_ROOT` | Racine de l'API ProConnect. | *(déduit du domaine)* | ⚪ |
| `PROCONNECT_USER_CREATION_FILTER` | Filtre restreignant les comptes créés (ex. par domaine e-mail). | *(vide)* | ⚪ |
| `SF_DISABLE_LOCAL_LOGIN` | Désactive la connexion par identifiant/mot de passe classique (ProConnect uniquement). | `False` | ⚪ |
| `LASUITE_DOMAINE_API_KEY` | Clé API La Suite (intégration domaine). | *(vide)* | ⚪ |

## Affichage et divers

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `SITE_NAME` | Nom du site affiché dans l'administration Wagtail. | `Sites Conformes` | 🟠 |
| `WAGTAILADMIN_PATH` | Adresse de la page d'administration. | `cms-admin/` | ⚪ |
| `SF_DISABLE_TUTORIALS` | Masque le panneau de tutoriels dans le back-office. | `False` | ⚪ |
| `SF_SCHEME_DEPENDENT_SVGS` | Adapte les SVG au thème clair/sombre. | `False` | ⚪ |
| `WAGTAILDOCS_MAX_UPLOAD_SIZE` | Taille maximale des documents téléversés (en octets). | `10485760` (10 Mo) | ⚪ |
| `DSFR_USE_INTEGRITY_CHECKSUMS` | Active les sommes de contrôle d'intégrité du DSFR (peut entrer en conflit avec WhiteNoise). | `False` | ⚪ |

## Supervision des erreurs (Sentry)

| Variable | Rôle | Défaut | Niveau |
| --- | --- | --- | --- |
| `SENTRY_DSN` | Adresse du projet Sentry. Sa présence active la remontée d'erreurs. | *(vide)* | ⚪ |
| `SENTRY_ENVIRONMENT` | Nom de l'environnement signalé à Sentry. | `production` | ⚪ |
