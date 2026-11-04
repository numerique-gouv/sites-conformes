# Changer de nom de domaine

Cette page décrit comment faire répondre un site Sites Conformes sur un nouveau
nom de domaine, quelle que soit la méthode d’hébergement. Elle s’applique
notamment :

- au passage de l’adresse de test (par exemple `mon-site.osc-fr1.scalingo.io`)
au **domaine définitif** (par exemple `mon-site.gouv.fr`) ;
- au **renommage** d’un site déjà en service ;
- à la **bascule du domaine** à la fin d’une migration d’hébergement (voir
{doc}`migrer-hebergement` pour la procédure complète).

## Pourquoi le domaine est stocké à deux endroits

Dans Sites Conformes, le nom de domaine du site vit **à la fois** :

- dans les **variables d’environnement** (`HOST_URL`, `ALLOWED_HOSTS`), lues
au démarrage de l’application ;
- dans la **base de données**, comme nom d’hôte du site.

Si l’un des deux n’est pas mis à jour, le site continue de fonctionner en
apparence mais génère des liens vers l’ancien domaine : liens des e-mails
(réinitialisation de mot de passe, notifications), prévisualisations, plan du
site (`/sitemap.xml`), adresses absolues des pages… Un domaine absent
d’`ALLOWED_HOSTS` provoque quant à lui des erreurs 400 (*Bad Request*) et des
erreurs CSRF à la connexion au back-office.

## Étape 1 — Brancher le domaine

Faites pointer le domaine vers l’hébergement (enregistrement DNS auprès de votre
registrar ou de votre service informatique), puis déclarez-le côté hébergeur :

- **Scalingo** : voir {ref}`scalingo-domaine-definitif` ;
- **serveur Linux** : ajoutez le domaine au reverse proxy et à son certificat
TLS (voir {doc}`serveur-linux`) ;
- **Docker** : idem, au niveau du reverse proxy placé devant les conteneurs
(voir {doc}`docker`).

## Étape 2 — Mettre à jour les variables d’environnement

| Variable | Nouvelle valeur |
| --- | --- |
| `ALLOWED_HOSTS` | ajoutez le nouveau domaine. Gardez l’ancien, séparé par une virgule, le temps de la transition |
| `HOST_URL` | le nouveau domaine, **nom de domaine seul**, sans `https://` ni port |
| `WAGTAILADMIN_BASE_URL` | à modifier **seulement si vous l’aviez définie** ; sinon elle est reconstruite à partir de `HOST_URL` |
| `CSRF_TRUSTED_ORIGINS` | à modifier **seulement si vous l’aviez définie** ; sinon elle est reconstruite à partir de `ALLOWED_HOSTS` |

Redémarrez l’application pour qu’elle prenne en compte les nouvelles valeurs
(Scalingo le fait automatiquement à chaque modification des variables).

Voir {doc}`variables-environnement` pour le détail de chaque variable.

## Étape 3 — Répercuter le domaine en base de données

```sh
python manage.py set_config
```

Cette commande réécrit le nom d’hôte du site Wagtail à partir de `HOST_URL`
(et le port à partir de `HOST_PORT` s’il est défini). Elle **n’est pas lancée
automatiquement** lors des déploiements : pensez à la lancer vous-même, sous la
forme propre à votre hébergement (`scalingo -a mon-site run …`,
`docker compose exec web …`, etc.).

Il est aussi possible de définir ces valeurs dans l’administration : dans
« Paramètres » → « Sites », cliquer sur le nom du site concerné et mettre à jour
la valeur « Nom d’hôte » (et éventuellement le port)

:::{warning}
La commande `set_config` agit sur le site par défaut uniquement. Si vous voulez
configurer un autre site, il faut définir ces valeurs via l’interface
d’administration.
:::

## Étape 4 — Vérifier

- Le site public répond sur le nouveau domaine, en HTTPS.
- La connexion au back-office fonctionne (`/cms-admin/` par défaut).
- L’e-mail « mot de passe oublié » contient un lien vers le nouveau domaine.
- Le plan du site (`/sitemap.xml`) liste des adresses sur le nouveau domaine.
- Dans le back-office, **Paramètres → Sites** affiche le nouveau nom d’hôte.

## Et l’ancien domaine ?

Une fois la transition terminée, deux options :

- **le rediriger** vers le nouveau domaine, au niveau de l’hébergeur ou du
reverse proxy (recommandé si l’ancienne adresse a circulé) ;
- **le retirer** d’`ALLOWED_HOSTS` s’il n’est plus utilisé.

## Cas particulier : base de production chargée en local

Une base de données copiée depuis la production contient le domaine de
production. Après l’avoir restaurée en local, lancez `set_config` pour
réécrire le nom d’hôte avec votre `HOST_URL` locale. Voir
{doc}`../donnees/sauvegarde-restauration`.
