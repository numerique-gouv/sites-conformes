# Stockage des médias en base de données (DB Storage)

## Contexte

Sur les plateformes PaaS (Scalingo, Heroku, Clever Cloud) ou les déploiements Docker, le système de fichiers est souvent **éphémère** : chaque redéploiement efface les fichiers uploadés (images, documents).

Sites Conformes propose trois backends de stockage pour les médias :

| Priorité | Backend | Variable d'activation | Cas d'usage |
|----------|---------|----------------------|-------------|
| 1 | **S3** (Object Storage) | `S3_HOST` | Production avec stockage S3 compatible |
| 2 | **PostgreSQL** (DB Storage) | `SF_USE_DB_STORAGE=1` | PaaS sans S3, Docker, Plesk |
| 3 | **Système de fichiers** | _(par défaut)_ | Développement local |

## Activation

Ajoutez dans votre fichier `.env` :

```env
SF_USE_DB_STORAGE=1
```

Puis relancez l'application. Les médias seront stockés directement dans la base de données PostgreSQL.

> **Note** : Si `S3_HOST` est configuré, le S3 est prioritaire et `SF_USE_DB_STORAGE` est ignoré.

## Fonctionnement

- Les fichiers sont stockés dans la table `db_storage_storedfile` sous forme binaire (`BinaryField`).
- Les images et documents uploadés via l'admin Wagtail sont automatiquement sauvegardés en base.
- Les fichiers sont servis via l'URL `/db-storage/serve/?name=<chemin>`.
- Un header `Cache-Control: public, max-age=3600` est appliqué pour le cache navigateur.

## Migration depuis S3

Si vous utilisez actuellement S3 et souhaitez passer au stockage en base de données :

### 1. Transférer les fichiers

Avec S3 encore configuré dans votre `.env`, lancez :

```bash
python manage.py migrate_s3_to_db
```

Cette commande :
- Se connecte au bucket S3 avec les credentials de votre `.env`
- Télécharge tous les fichiers et les stocke dans la table `StoredFile`
- Met à jour les URLs S3 codées en dur dans les révisions Wagtail et les champs texte

### 2. Options disponibles

```bash
# Simulation sans modification
python manage.py migrate_s3_to_db --dry-run

# Transférer uniquement les fichiers (sans mise à jour des URLs)
python manage.py migrate_s3_to_db --skip-urls

# Mettre à jour uniquement les URLs (fichiers déjà transférés)
python manage.py migrate_s3_to_db --skip-files
```

### 3. Basculer le backend

Une fois les fichiers transférés, modifiez votre `.env` :

```env
# Supprimer ou vider S3_HOST
S3_HOST=

# Activer le stockage en base
SF_USE_DB_STORAGE=1
```

Redémarrez l'application. Les images et documents s'afficheront depuis la base de données.

## Migration depuis le système de fichiers

Si vos médias sont sur le système de fichiers local :

```bash
python manage.py migrate_files_to_db
```

Options :
- `--dry-run` : simule la migration sans modifier la base

## Limitations

- **Performance** : Le stockage en base est plus lent que S3 ou le système de fichiers pour les gros volumes. Adapté aux sites avec un volume modéré de médias (quelques centaines de fichiers, moins de 500 Mo).
- **Taille de la base** : Les fichiers augmentent la taille de la base PostgreSQL et donc des sauvegardes.
- **Pas de CDN** : Contrairement au S3, les fichiers ne bénéficient pas d'un CDN. Le header `Cache-Control` permet toutefois la mise en cache côté navigateur.

## Architecture technique

```
db_storage/
├── models.py     # Modèle StoredFile (BinaryField)
├── storage.py    # Backend DatabaseStorage (API Django Storage)
├── views.py      # Vue de service des fichiers
├── urls.py       # Route /db-storage/serve/
└── management/commands/
    ├── migrate_files_to_db.py  # Migration filesystem → DB
    └── migrate_s3_to_db.py     # Migration S3 → DB
```
