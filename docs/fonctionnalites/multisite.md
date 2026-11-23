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

## Hébergement

Chaque site doit répondre à son nom de domaine : ajoutez-les tous à
`ALLOWED_HOSTS`. Sur Scalingo, ne définissez pas de domaine canonique (voir
{ref}`scalingo-plusieurs-sites`).

## Créer un site

La commande `create_site` crée un site prêt à recevoir ses contributeurs :

```sh
python manage.py create_site --hostname site-c.example.org --name "Site C" --locales fr,en
```

| Option | Rôle |
| --- | --- |
| `--hostname` | Nom de domaine du site, sans protocole ni port. Obligatoire. |
| `--name` | Nom du site, repris par ses groupes, sa collection et son workflow. Obligatoire. |
| `--port` | Port du site. Par défaut : `HOST_PORT`, ou 80. |
| `--locales` | Langues du site, séparées par des virgules. La première est celle de la page d’accueil. Par défaut : la langue par défaut de l’instance. |
| `--with-starter-pages` | Crée aussi les pages « Mentions légales », « Déclaration d’accessibilité » et « Contact », avec leurs liens dans les menus. |

La commande crée :

- une page d’accueil, placée à la racine de l’arbre des pages, à côté de celles
  des autres sites, et sa traduction dans chaque langue ;
- le site (**Paramètres → Sites**) ;
- une collection d’images et de documents, au nom du site ;
- trois groupes, `<nom> – Administrateurs`, `<nom> – Modérateurs` et
  `<nom> – Éditeurs`, avec les droits décrits ci-dessous, sur la page
  d’accueil et sur chacune de ses traductions ;
- le workflow « Validation `<nom>` », dont l’approbation revient aux
  modérateurs et aux administrateurs du site, appliqué à la page d’accueil et
  à ses traductions ;
- dans chaque langue, un menu principal (avec un lien vers l’accueil) et un
  menu de pied de page vides ;
- la configuration du site, avec le sélecteur de langue si le site a plusieurs
  langues.

Elle ne modifie aucun autre site, ni les groupes existants.

**Relancer la commande** avec le même nom d’hôte et le même port ne crée aucun
doublon : elle complète le site. Le nom d’un site existant n’est pas modifié.

### Ajouter une langue à un site

Traduisez la page d’accueil du site depuis l’administration, comme d’habitude
(bouton **Traduire** de la page d’accueil), ou relancez `create_site` avec la
nouvelle langue (`--locales fr,en,de`).

Dans les deux cas, la page d’accueil traduite reçoit les droits de page et le
workflow de la page d’accueil du site. Sans cela, elle n’en aurait aucun : les
pages d’accueil traduites sont placées à côté de la page d’accueil dans l’arbre,
et non en dessous. Le menu principal et le menu de pied de page de la nouvelle
langue sont créés par `create_site`, ou depuis **Menus** dans l’administration.

### Droits des groupes

| Droit | Administrateurs | Modérateurs | Éditeurs |
| --- | --- | --- | --- |
| Pages du site | créer, modifier, publier, verrouiller, supprimer avec les sous-pages | créer, modifier, publier, verrouiller, supprimer une page sans sous-page | créer, modifier, soumettre à validation, supprimer un brouillon sans sous-page |
| Images et documents de la collection du site | oui | oui | oui |
| Pictogrammes DSFR et illustrations par défaut | choisir | choisir | choisir |
| Catégories, organisations, personnes | oui | oui | oui |
| Menus | oui | oui | non |
| Configuration et scripts personnalisés du site | oui | non | non |
| Redirections | oui | non | non |

Les droits sur la configuration et les scripts sont donnés pour le site
seulement : un administrateur ne modifie pas ceux des autres sites.

Les groupes n’ont aucun droit sur les comptes : un droit global sur les
comptes permettrait de modifier tous les comptes de l’instance, y compris
ceux des superadministrateurs. Seul un superadministrateur ajoute une
personne aux groupes d’un site.

### Images installées

Les pictogrammes du DSFR et les illustrations par défaut des blocs sont
partagés par tous les sites : les groupes de chaque site peuvent les choisir,
mais seul un superadministrateur peut les modifier ou les supprimer.
`create_site` ne les importe que si leurs collections n’existent pas encore,
sans jamais les dupliquer ni les remplacer.

Les images par défaut des blocs sont cherchées uniquement dans ces deux
collections : une image d’un site portant le même titre n’est jamais reprise.

### Ce que la commande ne fait pas

- **Nom de domaine :** ajoutez le nom d’hôte à la variable `ALLOWED_HOSTS`,
  et configurez le DNS et le certificat. La commande avertit si le nom
  d’hôte n’est pas dans `ALLOWED_HOSTS`.
- **Cloisonnement :** si `SF_MULTISITE_ISOLATION_ENABLED` est désactivée, la
  commande le signale et liste les groupes sans droit de page : ils n’auront
  accès à aucun site une fois le cloisonnement activé.
- **Comptes :** ajoutez les personnes aux groupes du site depuis
  **Paramètres → Utilisateurs**.

### Pages de démarrage d’un site existant

Pour créer les pages « Mentions légales », « Déclaration d’accessibilité » et
« Contact » dans un site qui existe déjà, indiquez son identifiant (visible dans
l’adresse de **Paramètres → Sites**) :

```sh
python manage.py create_starter_pages --site <identifiant>
```

Une page dont le slug existe déjà dans ce site n’est pas recréée. Sans
`--site`, la commande garde son comportement : elle prépare le site par défaut
d’une nouvelle instance.

## Message au déploiement

Si l’instance a plusieurs sites et que la variable est désactivée, Django
affiche un message d’information (`sites_conformes_core.I001`) lors de
`migrate`, donc à chaque déploiement.

Ce message ne bloque rien. Il n’appelle aucune action si l’absence de
cloisonnement est voulue.

Pour l’afficher à tout moment :

```sh
python manage.py check --database default
```
