# Gestion de la base de données et des médias

Une instance Sites Conformes conserve ses données à **deux endroits distincts** :

- **la base PostgreSQL** : les pages, les comptes, les réglages, bref tout le contenu éditorial et la configuration ;
- **les fichiers médias** : les images et documents téléversés, stockés selon le mode choisi — système de fichiers, S3, ou base PostgreSQL (voir {doc}`stockage-medias`).

Sauvegarder ou transférer « les données » d'un site signifie donc toujours manipuler **ces deux éléments ensemble** : une base sans ses médias (ou l'inverse) donne un site incomplet.

Le projet fournit un ensemble de scripts pour sauvegarder, restaurer et transférer ces données. Ils s'adressent surtout au **travail en local** (développement) : se prémunir avant une manipulation risquée, ou récupérer les données de production pour reproduire un comportement observé en ligne.

> ℹ️ Ces opérations passent par des recettes `just` regroupées dans la catégorie **« Dev DB and medias management »**. Tapez `just` pour afficher la liste complète.

## Deux scénarios

La plupart des besoins se ramènent à l'un de ces deux cas :

1. **Gérer une sauvegarde locale** — vous faites une copie de votre base et de vos médias de dev *avant* une opération risquée (test d'une migration, import massif…), pour pouvoir revenir en arrière. → `backup-local`, puis au besoin `restore-local`.
2. **Récupérer les données de production** — vous rapatriez en local l'état exact de la production, par exemple pour reproduire un bug. → `descend-prod`, puis `restore-prod`.

> 🔁 **Télécharger n'est pas restaurer.** `descend-prod` **télécharge** la dernière sauvegarde de production dans votre répertoire de sauvegardes ; c'est `restore-prod` qui **charge** ensuite ces données dans votre base et vos médias locaux. Les deux étapes sont séparées pour que vous puissiez inspecter ou conserver le téléchargement avant de l'appliquer.

## Où vivent les sauvegardes ?

- **En production (Scalingo)** : la base PostgreSQL est sauvegardée **automatiquement** par la plateforme — vous pouvez consulter et télécharger ces sauvegardes depuis l'interface de l'addon PostgreSQL. Les médias, eux, résident sur le stockage S3.
- **En local** : les sauvegardes et les téléchargements sont écrits dans le répertoire défini par la variable `BACKUP_DIR`.

## Prérequis et configuration

**Pour les sauvegardes locales**, définissez `BACKUP_DIR` dans votre `.env`, en pointant vers un répertoire **situé hors du projet Django** — pour ne pas risquer de committer une sauvegarde par erreur.

**Pour manipuler les données de production**, il faut en plus :

- la **CLI Scalingo** (pour récupérer la dernière sauvegarde de base de données) — voir [installation](https://doc.scalingo.com/tools/cli/start) et [connexion](https://doc.scalingo.com/tools/cli/introduction) ;
- le paquet **[rclone](https://rclone.org/)** (`apt install rclone`) pour récupérer les fichiers médias depuis le S3 ;
- les variables suivantes dans votre `.env` :

```sh
PROD_APP=            # nom de l'app Scalingo, par ex. sites-conformes
PROD_DB_NAME=        # nom de la base dans Scalingo, par ex. sites_facil_123
PROD_S3_BUCKET_NAME=
PROD_S3_LOCATION=
RCLONE_CONFIG_MYS3_REGION_NAME=
RCLONE_CONFIG_MYS3_ENDPOINT=
RCLONE_CONFIG_MYS3_ACCESS_KEY_ID=
RCLONE_CONFIG_MYS3_SECRET_ACCESS_KEY=
RCLONE_CONFIG_MYS3_PROVIDER=Other
RCLONE_CONFIG_MYS3_TYPE="s3"
```

Le préfixe `RCLONE_CONFIG_MYS3_*` permet à `rclone` de récupérer automatiquement ces paramètres depuis l'environnement.

## Sauvegarder et restaurer les données locales

Faire une sauvegarde de la base et des médias de votre instance locale :

```sh
just backup-local
```

La restaurer plus tard (base **et** médias) :

```sh
just restore-local
```

Vous pouvez ne cibler qu'une des deux moitiés avec `just restore-local-db` ou `just restore-local-medias`. Pour repartir d'une base vide, `just clear-local-db`.

> ⚠️ Faites **toujours** un `just backup-local` avant de remplacer vos données locales par une sauvegarde ou par les données de production : sinon vos données de dev actuelles sont perdues.

## Récupérer les données de production

Télécharger la dernière sauvegarde de production (base + médias) :

```sh
just descend-prod
```

Puis la charger dans votre environnement local :

```sh
just restore-prod
```

Là encore, des variantes permettent de ne traiter qu'une moitié : `descend-prod-db` / `descend-prod-medias` pour le téléchargement, `restore-prod-db` / `restore-prod-medias` pour la restauration.

> 🏷️ Après avoir chargé des données de production en local, lancez `python manage.py set_config` pour réécrire l'`HOST_URL` en base : sans cela, votre site local continuerait de pointer vers le domaine de production.

## Aide-mémoire des recettes

| Recette | Effet |
| --- | --- |
| `just backup-local` | Sauvegarde la base **et** les médias locaux dans `BACKUP_DIR` |
| `just restore-local` | Restaure la dernière sauvegarde locale (base + médias) |
| `just restore-local-db` · `just restore-local-medias` | Idem, base ou médias uniquement |
| `just clear-local-db` | Vide la base locale |
| `just descend-prod` | Télécharge la dernière sauvegarde de production (base + médias) |
| `just descend-prod-db` · `just descend-prod-medias` | Idem, base ou médias uniquement |
| `just restore-prod` | Restaure les données de production téléchargées (base + médias) |
| `just restore-prod-db` · `just restore-prod-medias` | Idem, base ou médias uniquement |
