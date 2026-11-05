# Données de test multisite

Pour développer et tester les fonctionnalités multisites, le projet fournit deux
sites fictifs, toujours les mêmes, utilisés à trois endroits :

- les **tests automatisés** (`MonositeTestCase` et `MultisiteTestCase`) ;
- la **commande `setup_multisite_demo`**, qui les crée dans votre base locale ;
- les **bases de référence**, des fixtures versionnées qui servent à tester les
  migrations de données.

Aucune donnée réelle n’est utilisée : les sites, les contenus, les personnes et
les comptes sont inventés.

## Les deux sites

Ce sont les sites de deux administrations centrales fictives, inspirées du
*Petit Prince*.

| Élément | Site A | Site B |
| --- | --- | --- |
| **Nom** | Ministère des Lampadaires et des Planètes | Direction générale du Recensement des étoiles |
| **Adresse** | `site-a.localhost` | `site-b.localhost` |
| **Arborescence** | Peu profonde : Le ministère, Vos services, Actualités, Contact | Plus profonde : Démarches > Par planète > Fiches, Recensement, Agenda, Actualités, Contact |
| **Menu principal** | Mega-menu « Le ministère » à deux colonnes (Découvrir le ministère, Vos services), puis des liens | Sous-menus « Démarches » et « Nous connaître », et des liens |
| **Biographie** | Le ministre, Luc Falotier | La ministre déléguée, Najma Al-Biruni |
| **Contenus datés** | Blog d’une dizaine d’articles | Agenda d’une dizaine d’événements, et un petit blog |
| **Catégories** | Hiérarchie : Éclairage > Lampadaires | À plat |
| **Anglais** | Tout le site est traduit | Accueil et quelques pages seulement |
| **Sélecteur de langue** | Activé (mode simple) | Activé (mode simple) |

Chaque site a sa collection d’images, ses menus, sa configuration, trois groupes
(`<site> – Administrateurs`, `– Modérateurs`, `– Éditeurs`) et un workflow
« Validation » approuvé par ses modérateurs et ses administrateurs.

Certains éléments sont **volontairement communs** aux deux sites, pour révéler
les collisions :

- les slugs de pages `actualites`, `contact`, `mentions-legales` et
  `accessibilite` ;
- la catégorie « Actualités », l’organisation « Bureau des longitudes » et la
  personne « Camille Roux », utilisées par les deux sites.

D’autres ne sont utilisés par aucun site : la catégorie « Archives »,
l’organisation « Commission des astéroïdes » et la personne « Paul Verdier ».

Les contenus sont décrits dans `sites_conformes/core/demo_data/content.json`, et
les images dans `sites_conformes/core/demo_data/img/` (sources et licences dans
`CREDITS.md`). Ce dossier n’est pas inclus dans le paquet publié.

## Les comptes

Tous les comptes ont le mot de passe `demo-sites-conformes`.

| Compte | Groupes |
| --- | --- |
| `superadmin` | Superadministrateur |
| `admin-a`, `moderateur-a`, `editeur-a` | Administrateurs, Modérateurs ou Éditeurs du site A |
| `admin-b`, `moderateur-b`, `editeur-b` | Administrateurs, Modérateurs ou Éditeurs du site B |
| `editeur-ab` | Éditeurs du site A et Éditeurs du site B |

En monosite, un seul site existe (A par défaut, ou B), avec le compte
`superadmin` et les trois comptes de ce site. Ce site est alors le site par
défaut de l’instance.

## Dans les tests

Faites hériter vos tests de l’une des deux classes de
`sites_conformes/core/tests/base.py` :

- `MonositeTestCase` crée le site A seul, avec `SF_MULTISITE_ISOLATION_ENABLED`
  désactivé (pour le site B seul, redéfinissez `site_keys = ("b",)`) ;
- `MultisiteTestCase` crée les sites A et B, avec `SF_MULTISITE_ISOLATION_ENABLED`
  activé.

Les sites sont créés une fois par classe, sans images. Les objets créés sont
disponibles dans `self.site_a`, `self.site_b` (`None` en monosite) et
`self.users["editeur-a"]`, etc.

Pour qu’un test tourne dans les deux configurations, écrivez-le dans une classe
*mixin*, puis déclarez une sous-classe par configuration. Exemple :
`sites_conformes/core/tests/test_demo_sites.py`.

## En local

Sur une base vide (par exemple après `just clear-local-db` puis
`just migrate`) :

```sh
just demo-multisite-setup
```

La commande refuse de s’exécuter si `DEBUG` est faux ou si la base contient déjà
des pages. Options : `--monosite` pour ne créer que le site A, `--monosite b`
pour ne créer que le site B, `--without-media` pour ne pas importer les images.

Les adresses `*.localhost` pointent vers votre machine sans configuration : ouvrez
`http://site-a.localhost:<port>/` et `http://site-b.localhost:<port>/`.

## Les bases de référence

Les fixtures `site-a.json` et `site-b.json`, dans
`sites_conformes/core/demo_data/fixtures/`, sont des exports des sites de démo,
**une par site**. Elles servent à vérifier que les migrations de données
(catégories, organisations, personnes) transforment correctement une base
existante.

Chaque fixture contient son site (pages, révisions, menus, configuration,
collection, groupes, workflow, comptes) et tous les objets partagés (page
racine, pictogrammes, catégories, organisations, personnes, superadmin). Les
objets partagés sont identiques dans les deux fixtures : on peut donc les
charger seules ou ensemble. Le compte `editeur-ab`, membre des deux sites,
n’est dans aucune : il est recréé quand les deux sites sont chargés.

| Base | Sites | Base de données |
| --- | --- | --- |
| `monosite` | A seul | `<DATABASE_NAME>_ref_monosite` |
| `monosite-b` | B seul, site par défaut | `<DATABASE_NAME>_ref_monosite_b` |
| `multisite` | A et B | `<DATABASE_NAME>_ref_multisite` |

Pour charger une base de référence **dans une base de données et un dossier de
médias séparés**, sans toucher à votre base locale habituelle :

```sh
just reference-load-db multisite        # ou monosite, monosite-b
just reference-runserver multisite
just reference-django multisite <commande>   # par exemple migrate ou shell
```

Les médias sont dans `medias_ref_<base>/`. Les recettes ne fonctionnent
qu’avec PostgreSQL en
local, pas avec Docker.

Le serveur écoute sur `127.0.0.1`, au port `HOST_PORT` (8000 s’il est vide) :
ouvrez `http://site-a.localhost:<port>/`. Les fixtures ne contiennent pas le
port de la machine qui les a exportées : au chargement, les sites prennent ce
port, et les liens du back-office (« Voir en ligne ») pointent au bon endroit.
Si votre navigateur ne résout pas `*.localhost`, ajoutez
`127.0.0.1 site-a.localhost site-b.localhost` à `/etc/hosts`.

:::{important}
**Une fixture se charge avec les modèles du code qui l’a exportée.** Une fois
les nouvelles migrations écrites, la commande refuse de charger la fixture et
indique le commit d’export, enregistré dans les fichiers
`site-*.manifest.json`. Pour
tester une migration :

1. extrayez ce commit (`git switch --detach <commit>`) ;
2. lancez `just reference-load-db multisite` ;
3. revenez sur votre branche, puis lancez
   `just reference-django multisite migrate` ;
4. vérifiez le résultat, puis le retour arrière
   (`just reference-django multisite migrate <app> <migration précédente>`).
:::

### Régénérer les bases de référence

Ne régénérez les fixtures que si les sites de démo changent, et **jamais après
les migrations qu’elles servent à tester** : elles doivent refléter le schéma de
la dernière version publiée.

```sh
just reference-export
```

La recette crée une base temporaire avec les deux sites (`setup_multisite_demo`),
puis `export_reference_base` répartit chaque objet entre les sites et écrit une
fixture et un manifeste par site. L’export échoue si un objet d’un site en
référence un de l’autre site, car la fixture ne pourrait plus se charger seule.
La base temporaire est ensuite supprimée. Elle a besoin des fichiers statiques
(`just collectstatic`) pour les pictogrammes du DSFR.
