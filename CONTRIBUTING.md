# Contribuer au site numerique.gouv.fr

## Installation

Une documentation détaillée de l’installation en local est disponible sur [ONBOARDING.md](./ONBOARDING.md).

```sh
git clone https://github.com/numerique-gouv/numerique-gouv-cms
cd numerique-gouv-cms
```

Tant que ce dépôt reste un fork de [Sites Conformes](https://github.com/numerique-gouv/sites-conformes), ajouter aussi le remote `upstream` (voir [ONBOARDING.md](./ONBOARDING.md#ajouter-le-remote-upstream)).

### Effectuer les tests

Les tests unitaires peuvent être lancés avec `just test`.

Cela lance les tests en parallèle pour gagner du temps, mais en cas d’échec, il est possible de les lancer
séquentiellement via `just unittest`

Vous pouvez également générer un rapport sur la couverture de tests :

```sh
just coverage
```

Pour toutes ces commandes, il est possible via `just` de cibler une application Django spécifique, par exemple :

```sh
just test content_manager
just unittest blog
just coverage events
```

### Tests end-to-end

Les tests end-to-end utilisent [Playwright](https://playwright.dev/) et se trouvent dans le dossier `e2e/`.
En local, ils tournent dans Docker (profil `e2e` du fichier `docker-compose.yml`) : il n’est pas nécessaire
d’installer Node ni Chromium, et ils utilisent une base de données jetable, distincte de la base de développement.

```sh
# Lance les tests (le premier lancement construit l’image et prépare la base, ce qui prend quelques minutes)
just e2e

# Arrête les conteneurs et réinitialise la base e2e
just e2e-down
```

`just e2e` démarre trois conteneurs :

- `db-e2e` : une base PostgreSQL jetable ;
- `web-e2e` : le serveur Django avec `DEBUG=False` (pour obtenir les vraies pages d’erreur, comme en CI),
  et le contenu créé par `just e2e-setup` (pages de base, pages de démo et pages de la commande `create_e2e_pages`) ;
- `playwright` : l’image officielle de Playwright, qui lance les tests.

Les conteneurs `db-e2e` et `web-e2e` restent démarrés entre deux lancements, pour aller plus vite.
Le code est monté dans les conteneurs : les modifications sont prises en compte sans reconstruire l’image.

Les arguments supplémentaires sont transmis à Playwright, par exemple `just e2e e2e/numerique.spec.ts`.
Le rapport HTML est généré dans le dossier `playwright-report/`.

Les tests marqués `@regression` comparent en plus une capture d’écran pleine page à une référence.
En CI, la référence est générée à partir de la branche `main`, puis comparée à la branche de la PR.
Une différence visuelle fait échouer la CI, sauf si la PR porte le label `visual-change`.
En local, `just e2e --update-snapshots --grep=@regression` génère la référence.

## Définition du fini

Avant chaque mise en production, les intervenant·es sont prié·es de [passer cette liste en revue](./DOD.md).

## Commandes

Le projet utilise [just](https://just.systems/) pour gérer le lancement de séries de commandes spéfiques, appelées recettes.

Il est possible d’avoir une liste des recettes implémentées en tapant simplement `just`.

Pour les commandes Django spécifiquement, il est possible d’en obtenir la liste avec la commande

```sh
uv run python manage.py
```

## Gestion des dépendances avec uv

Le projet utilise [uv](https://docs.astral.sh/uv/) pour gérer les dépendances de paquets Python et produire des *builds*
déterministes.

Pour installer le projet sans les dépendances de dev :

```sh
just init
```

Pour installer le projet avec les dépendances de dev :

```sh
just init-dev
```

Pour installer un nouveau paquet et l’ajouter aux dépendances :

```sh
uv add <paquet>
```

Pour un paquet ne servant que pour le développement, par exemple `debug-toolbar` :

```sh
uv add --dev <paquet>
```

## Configuration locale, production

Le projet utilise [django-dotenv](https://github.com/jpadilla/django-dotenv) pour gérer les settings des différents environnements ne pouvant être embarquées dans le dépôt git.

Typiquement :

* configuration locale spécifique à chaque intervenant·e sur le projet, e.g paramètres de connexion à la base de données ;
* configuration de production.

Pour surcharger la configuration locale de développement, il est nécessaire de créer un fichier `.env` à la racine du projet Django.
Cf. [le fichier .env.example](./src/.env.example) pour l’exemple.

En staging et en production, les variables d’environment sont spécifiées directement sur Scalingo.

## CSS

Le projet utilise [Le Système de design de l’État](https://www.systeme-de-design.gouv.fr/), par le biais de la librairie
[django-dsfr](https://github.com/numerique-gouv/django-dsfr)

Il est donc nécessaire d’utiliser autant que possible les classes spécifiques au Système de design de l’État dans le HTML.

## Traduction : À propos des fichiers `.po` et `.mo`

Ce project utilise le [système de traduction de Django](https://docs.djangoproject.com/en/dev/topics/i18n/translation/).

Le texte dans le code est en anglais et la traduction qui s’affiche sur le site en français, se trouve dans le fichier
`.po` du dossier `locales`.

Pour générer la traduction dans le fichier `.po` :

```sh
just makemessages
```

Django utilise une version compilée du fichier `.po`, c’est le fichier `.mo` que l’on obtient avec :

```sh
just compilemessages
```

Il est recommandé d’utiliser [https://poedit.net/](Poedit) pour les traductions, afin de profiter de sa mémoire de traduction
basée sur celles déjà existantes. Il produit directement le fichier `.mo` à la sauvegarde, il n’est donc pas nécessaire de le
compiler manuellement.

## Linter de code / Code Style

Nous utilisons `ruff` et `black` pour assurer un formatage cohérent du code sur l’ensemble du projet.

Pour vérifier son code, on peut intégrer le linter adapté à son IDE et ou lancer la commande suivante :

```sh
just quality
```

Pour s’assurer que cette vérification est faite de manière systématique, nous utilisons des *pre-commit hooks*, gérés par [prek](https://prek.j178.dev/) (compatible avec le fichier `.pre-commit-config.yaml`).

Ils sont installés par `just init-dev`, ou manuellement via :

```sh
prek install
```

Il est possible de faire une passe manuelle sur l’ensemble du code via `just quality`, ou

```sh
prek run --all-files
```

## Audit du code

Quelques recettes du groupe « Code audit » de `just` :

* `just check` lance le [framework de vérification système](https://docs.djangoproject.com/fr/stable/topics/checks/) de Django (il est possible de cibler des applications : `just check blog events`) ;
* `just cloc` compte les lignes de code par application. Il nécessite [cloc](https://github.com/AlDanial/cloc) (`sudo apt install cloc`) ;
* `just routes-count` donne une estimation du nombre de routes internes et externes.

## Déploiement

### Variables d’environnement

En production, les variables d’environment sont spécifiées directement sur [Scalingo](https://scalingo.com/).

### Envoi de courriels

Les courriels transactionnels sont envoyés via [Brevo](https://www.brevo.com/fr/).

En local vous avez la possibilité de visualiser les courriels dont le template n’est pas hébergé sur Brevo depuis le terminal.
Pour ce faire la variable `EMAIL_BACKEND` doit être définie avec `django.core.mail.backends.console.EmailBackend` dans votre fichier `.env`

### Fichiers media

Nous utilisons en production sur Scalingo un service d’« *Object Storage* » compatible avec l’API S3 (OVHcloud) pour le stockage de tous les fichiers medias.

#### URLs publiques et cache

Sans la variable `S3_PUBLIC_HOST`, les URLs des médias sont signées (`X-Amz-Signature`). La signature change à chaque affichage, donc ni le navigateur ni un proxy ne peuvent garder les fichiers en cache.

Si `S3_PUBLIC_HOST` est définie (en général avec la même valeur que `S3_HOST`) :

* les URLs ne sont plus signées et restent stables. Chez OVHcloud, il faut aussi définir `S3_ADDRESSING_STYLE=virtual` (URLs `bucket.hôte/clé`) : OVHcloud refuse les requêtes anonymes au format `hôte/bucket/clé` (erreur 400 « Not S3 request »), qui est la valeur par défaut (`path`) ;
* les images (`original_images/` et `images/`) sont envoyées avec une ACL `public-read`, objet par objet. OVHcloud ne gère pas les politiques de bucket, et une ACL publique sur le bucket permettrait d’en lister le contenu : le bucket reste donc privé ;
* les documents restent privés sur S3. Ils sont servis par Wagtail (`WAGTAILDOCS_SERVE_METHOD = "serve_view"`), qui vérifie les restrictions des collections privées avant d’envoyer le fichier.

Tous les fichiers envoyés reçoivent un en-tête `Cache-Control`, défini par `S3_CACHE_CONTROL`, ou à défaut `MEDIA_CACHE_CONTROL` (par défaut `public, max-age=3600`). Les noms de fichiers sont uniques (`file_overwrite=False`), on peut donc choisir une durée longue, par exemple `public, max-age=2592000`.

La commande `set_s3_cache_control` met à jour les objets envoyés avant ces réglages. Elle peut être relancée sans risque :

```sh
python manage.py set_s3_cache_control --public-read --dry-run  # aperçu
python manage.py set_s3_cache_control --public-read            # application
```

L’option `--public-read` rend les images publiques. Elle est automatique quand `S3_PUBLIC_HOST` est définie.

La commande ne traite que les fichiers connus de Wagtail (images, renditions, documents) : elle lit leurs noms dans la base au lieu de lister le bucket. Elle vérifie qu’une image est publique avec une requête anonyme, au lieu de lire son ACL. Elle n’a donc besoin que des droits que l’utilisateur S3 de l’app doit avoir de toute façon : `s3:GetObject`, `s3:PutObject` et, pour les images publiques, `s3:PutObjectAcl` (aussi requis à chaque envoi d’image quand `S3_PUBLIC_HOST` est définie). `s3:ListBucket` et `s3:GetObjectAcl` ne lui sont pas nécessaires.

#### Droits de l’utilisateur S3 (OVHcloud)

Politique à importer pour l’utilisateur S3 de l’app (espace client OVHcloud → Public Cloud → Object Storage → *Utilisateurs S3* → *Importer une politique (JSON)*), via un fichier `userPolicy.json` ayant le contenu suivant, en remplaçant `<S3_BUCKET_NAME>` par le nom du bucket :

```json
{
  "Statement": [
    {
      "Sid": "MediaObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": [
        "arn:aws:s3:::<S3_BUCKET_NAME>/*"
      ]
    },
    {
      "Sid": "ListMediaBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::<S3_BUCKET_NAME>"]
    }
  ]
}
```

`s3:ListBucket` porte sur le bucket lui-même : sa ressource est `arn:aws:s3:::<S3_BUCKET_NAME>`, sans `/*`.

| Droit | Utilisé pour |
| --- | --- |
| `s3:GetObject` | lecture des médias, `HEAD` de la commande `set_s3_cache_control` |
| `s3:PutObject` | envoi de fichiers, copie faite par la commande |
| `s3:PutObjectAcl` | images publiques, à l’envoi et dans la commande |
| `s3:DeleteObject` | suppression d’images et de documents dans Wagtail |
| `s3:AbortMultipartUpload`, `s3:ListMultipartUploadParts` | envoi de gros fichiers, que boto3 découpe en plusieurs morceaux |
| `s3:ListBucket` | listage du bucket par `rclone` (`just descend-prod-medias`, `just descend-prod-to-staging`) |

L’import **remplace** la politique existante : téléchargez-la d’abord, et reportez dans ce modèle les droits à conserver (par exemple sur d’autres buckets).

`s3:ListBucket` permet de lister le bucket avec les clés de l’app uniquement : il reste privé pour les requêtes anonymes. Avec ce droit, S3 répond 404 pour un objet absent, et la commande `set_s3_cache_control` le compte comme « missing ». Sans ce droit (la commande n’en a pas besoin), S3 répond 403, et la commande compte l’objet comme « unreadable (missing or access denied) ».

Un changement de politique peut mettre quelques minutes à s’appliquer chez OVHcloud : attendez avant de relancer la commande.

Pour passer un environnement en URLs publiques, dans cet ordre :

1. mettre à jour la politique de l’utilisateur S3 (voir ci-dessus) ;
2. déployer, avec `S3_CACHE_CONTROL` défini  (et `S3_ADDRESSING_STYLE=virtual` chez OVHcloud) ;
3. lancer `set_s3_cache_control --public-read` (voir ci-dessus) ;
4. définir `S3_PUBLIC_HOST` ;
5. relancer la commande, pour les images envoyées entre les étapes 3 et 4.

#### Stockage local

En local, il est possible d’utiliser simplement le stockage de fichiers local (`FileSystemStorage`) en laissant vide la variable `S3_HOST` dans le fichier `.env`.
Il est alors conseillé de définir la variable `MEDIA_ROOT` (par exemple à "medias") pour éviter la création de plusieurs répertoires de médias à la racine.
