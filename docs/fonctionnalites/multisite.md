# Multisite

## Contexte

Une même instance de Sites Conformes peut servir plusieurs sites, chacun avec
son nom de domaine et sa page d’accueil (dans l’administration :
**Paramètres → Sites**).

Le **cloisonnement multisite** limite chaque contributeur aux sites de ses
groupes : sur une instance à plusieurs sites, il n’agit que sur les contenus
de ces sites.

## Activation

Le cloisonnement est **désactivé** par défaut. Pour l’activer, renseignez la
variable d’environnement :

```sh
SF_MULTISITE_ISOLATION_ENABLED=True
```

Seule cette variable compte : le cloisonnement ne s’active pas tout seul quand
un deuxième site est créé. Une instance peut avoir plusieurs sites sans
cloisonnement, par exemple quand la même équipe gère tous les sites.

:::{important}
Avant d’activer le cloisonnement, vérifiez que chaque groupe a des droits de
page sur les sites qu’il doit gérer. Un groupe sans droit de page n’a accès à
aucun site, même sur une instance à un seul site.
:::

## Accès d’un contributeur à un site

Un contributeur a accès à un site si l’un de ses groupes a un droit de page
(**Paramètres → Groupes**, rubrique « Permissions de page ») portant sur :

- la page d’accueil du site ;
- l’une de ses traductions : les pages d’accueil traduites sont placées à côté
  de la page d’accueil dans l’arbre des pages, et non en dessous ;
- une page parente de la page d’accueil : un droit sur la racine de l’arbre
  donne ainsi accès à tous les sites ;
- une sous-page du site : un droit sur une seule rubrique suffit.

Si un site est placé sous la page d’accueil d’un autre site, un droit sur une
page du premier donne aussi accès au second, puisque cette page est aussi sous
sa page d’accueil.

Un superadministrateur a accès à tous les sites. Un compte désactivé n’a accès
à aucun site.

Ces règles ne remplacent pas les droits de page de Wagtail : elles définissent
le périmètre d’un contributeur, et ses droits de page continuent de dire ce
qu’il peut faire sur chaque page.

## Ce que voit un contributeur

Quand le cloisonnement est activé, un contributeur qui n’est pas
superadministrateur :

- ne voit que les **menus** (menu principal, menu en haut à droite, menu de
  bas de pied de page) de ses sites. Le champ « Site » ne propose que ces
  sites, et il est présélectionné quand il n’y en a qu’un. Les autres menus
  renvoient une erreur 404, même en saisissant leur adresse ;
- ne trouve dans le **sélecteur de pages** que les pages de ses sites, en
  recherche comme en navigation. Les liens déjà posés vers une page d’un autre
  site restent en place ;
- reçoit une erreur 404 dans l’**explorateur de pages** sur une page d’un
  autre site, dont le titre n’apparaît donc pas ;
- trouve sur le **tableau de bord** des raccourcis vers le site par défaut
  s’il en fait partie, et sinon vers le premier de ses sites.

Pour les menus, seuls comptent les groupes qui ont un droit sur les menus : un
contributeur modérateur du site A et éditeur du site B ne gère que les menus
du site A.

## Middleware

Le cloisonnement de l’explorateur, du sélecteur de pages, des actions groupées
et des traductions de menus passe par le middleware
`sites_conformes.core.middleware.MultisiteIsolationMiddleware`, à placer après
le middleware d’authentification. Il est déjà présent dans les réglages du
projet. Avec le paquet, ajoutez-le à vos réglages (voir
{doc}`../paquet/installation`).

Si le cloisonnement est activé sans ce middleware, Django affiche
l’avertissement `sites_conformes_core.W002`.

## Groupes sans droit de page

Un groupe qui a des droits sur les menus mais aucun droit de page n’a accès à
aucun site : avec le cloisonnement, ses membres perdent l’accès aux menus.
Sur une instance à plusieurs sites, que le cloisonnement soit activé ou non,
Django liste ces groupes dans l’avertissement `sites_conformes_core.W001`.

Pour le détail des modèles et des membres de chaque groupe :

```sh
python manage.py multisite_isolation_report
```

## Réservé au superadministrateur

Les mots-clés et les domaines autorisés de ProConnect sont communs à tous les
sites. Quand le cloisonnement est actif, seul un superadministrateur les gère
(**Fragments → Mot-clés** et **ProConnect → Whitelisted email domains**).

Les autres contributeurs ne voient pas ces entrées, même si l’un de leurs
groupes a des droits sur ces modèles. S’ils saisissent leur adresse, ils sont
renvoyés au tableau de bord avec le message « Désolé, vous n’avez pas les
autorisations pour accéder à cette zone. », comme sur toute page de
l’administration qui leur est interdite. Ce blocage passe aussi par le
middleware `MultisiteIsolationMiddleware`.

Sans cloisonnement, les droits des groupes s’appliquent comme avant.

### Mots-clés communs à tous les sites

Les mots-clés n’appartiennent à aucun site ni à aucune langue. C’est un choix
assumé :

- dans le champ « Mots-clés » d’une page, les suggestions comprennent ceux
  des autres sites ;
- un contributeur qui peut modifier une page crée un mot-clé en saisissant un
  nom qui n’existe pas encore. Le mot-clé est créé dès l’enregistrement du
  brouillon, avant toute validation, et il est aussitôt proposé aux
  contributeurs de tous les sites ;
- un mot-clé renommé ou supprimé par un superadministrateur l’est sur tous
  les sites.

## Hébergement

Chaque site doit répondre à son nom de domaine : ajoutez-les tous à
`ALLOWED_HOSTS`. Sur Scalingo, ne définissez pas de domaine canonique (voir
{ref}`scalingo-plusieurs-sites`).

## Messages au déploiement

Si l’instance a plusieurs sites et que la variable est désactivée, Django
affiche un message d’information (`sites_conformes_core.I001`) lors de
`migrate`, donc à chaque déploiement.

Ce message ne bloque rien. Il n’appelle aucune action si l’absence de
cloisonnement est voulue.

Les avertissements `sites_conformes_core.W001` (groupes sans droit de page) et
`sites_conformes_core.W002` (middleware absent) ne bloquent rien non plus.

Pour l’afficher à tout moment :

```sh
python manage.py check --database default
```
