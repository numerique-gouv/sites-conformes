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

Un superadministrateur a accès à tous les sites. Un compte désactivé n’a accès
à aucun site.

Ces règles ne remplacent pas les droits de page de Wagtail : elles définissent
le périmètre d’un contributeur, et ses droits de page continuent de dire ce
qu’il peut faire sur chaque page.

## Message au déploiement

Si l’instance a plusieurs sites et que la variable est désactivée, Django
affiche un message d’information lors de `migrate`, donc à chaque
déploiement :

```text
INFOS:
?: (sites_conformes_core.I001) L’instance a plusieurs sites et le cloisonnement multisite est désactivé : les contributeurs ne sont pas limités aux sites de leurs groupes.
    HINT: Pour les y limiter, activez la variable d’environnement SF_MULTISITE_ISOLATION_ENABLED.
```

Ce message ne bloque rien. Il n’appelle aucune action si l’absence de
cloisonnement est voulue.

Pour l’afficher à tout moment :

```sh
python manage.py check --database default
```
