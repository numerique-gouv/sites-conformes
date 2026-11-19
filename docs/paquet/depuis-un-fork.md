# Revenir d’un fork vers le paquet

Votre site tourne sur un *fork* de Sites Conformes, et chaque mise à jour vous
génère des conflits ? Cette page explique comment revenir à la version publiée
du paquet.

Le principe : vos personnalisations passent dans un projet à vous, tout le
reste vient du paquet — **et la base de données ne change pas**. Pages,
images, comptes, historique des contenus : tout reste en place.

## Pourquoi c’est possible

Le paquet et le dépôt, c’est le même logiciel : mêmes applications Django,
mêmes tables en base (`sites_conformes_core_…`, `sites_conformes_blog_…`).
Une base créée par un fork se lit telle quelle par un projet qui installe le
paquet, à condition que les deux soient à la même version.

Ce qui change, c’est l’endroit où vit votre code :

| | Avec un fork | Avec le paquet |
| --- | --- | --- |
| **Le code de Sites Conformes** | Dans votre dépôt, mêlé à vos modifications | Installé comme dépendance, jamais modifié |
| **Vos personnalisations** | Des modifications du code de Sites Conformes | Des fichiers de votre projet |
| **Une mise à jour** | Une fusion, souvent avec des conflits | Un changement de numéro de version |

:::{important}
**Faites d’abord un essai sur une copie de la base de production**, voir
{doc}`../donnees/sauvegarde-restauration` : vous verrez combien de temps ça
prend et ce qu’il reste à adapter.
:::

## 1. Mettre le fork à jour

Fusionnez la dernière version de Sites Conformes dans votre fork, puis
déployez-la.

C’est une dernière fusion, nécessaire : elle amène votre base au schéma de la
version du paquet que vous allez installer. Les deux doivent correspondre.

Si votre fork date d’avant la version 4.0, ses applications sont encore à la
racine du dépôt (`content_manager`, `blog`…) : la commande
`migrate_from_sites_faciles` renomme alors les tables, voir le
{doc}`../changelog`.

## 2. Faire l’inventaire de vos modifications

Listez ce que votre fork a changé par rapport au dépôt officiel :

```sh
git remote add upstream https://github.com/numerique-gouv/sites-conformes
git fetch upstream
git diff --stat upstream/main...HEAD
```

`git remote add` déclare le dépôt officiel sous le nom `upstream` ;
`git diff --stat` liste les fichiers ajoutés ou modifiés dans votre fork.

Chacune de ces modifications a sa place dans le nouveau projet :

| Dans le fork | Dans le projet |
| --- | --- |
| Réglages, variables d’environnement | `config/settings.py` et `.env` |
| Gabarits modifiés | Dossier `templates/` à créer dans le projet, au même chemin |
| CSS, JavaScript, images | Dossier `static/` à créer dans le projet, en tête de `STATICFILES_DIRS` |
| Applications ajoutées | Copiées telles quelles : même nom, mêmes tables |
| Page de résultats de recherche | Réglage `SEARCH_VIEW`, voir {doc}`recherche` |
| Champs ou blocs ajoutés aux pages | Votre modèle de page, voir {doc}`modele-de-page-personnalise` |
| Correctifs utiles à tous | Une contribution au dépôt, voir {doc}`../contrib/guide-contribution` |

Au passage, triez : certaines modifications ont peut-être été intégrées à
Sites Conformes depuis, d’autres ne servent plus.

:::{warning}
**Seul le modèle des pages de contenu (`ContentPage`) peut être remplacé.**
Si votre fork a touché à d’autres modèles du paquet (blog, événements,
formulaires, menus), cette page ne suffit pas : proposez ces changements au
dépôt officiel, ou renoncez-y.
:::

## 3. Créer le projet

Créez un projet neuf avec `bouture` (étape 1 de {doc}`nouveau-projet`
seulement). Ne lancez ni `migrate` ni `create_starter_pages` : votre base
contient déjà vos pages.

Répondez aux questions de `bouture` d’après les fonctionnalités activées sur
votre fork (ProConnect, stockage des médias, langues…). Puis :

1. Reportez dans le projet les éléments de l’inventaire.
2. Faites pointer `DATABASE_URL` vers la copie de votre base.
3. Reprenez le stockage des médias du fork, avec les mêmes variables
   d’environnement : les images et documents restent à leur place.

:::{note}
**Le projet généré est plus léger que votre fork** : il n’inclut le tableau de
bord du back-office (`sites_conformes.dashboard`) que si vous choisissez
ProConnect ou la 2FA, et il ne déclare pas l’API `/api/v2/`. Si vous les
utilisez, ajoutez-les à la main — le dossier
[`config/`](https://github.com/numerique-gouv/sites-conformes/tree/main/config)
du dépôt sert de modèle.
:::

## 4. Reprendre vos modifications des pages de contenu

Passez cette étape si votre fork n’a pas modifié le modèle `ContentPage`.

Sinon, vos pages ont en base des colonnes que le paquet ne connaît pas.
Déclarez dans votre projet un modèle de page qui porte ces champs, puis
déplacez les pages existantes vers ce modèle avec `bern` : voir
{ref}`changer-de-modele-site-existant`.

Déclarez **tous** les champs que le fork avait ajoutés à `ContentPage` :
`bern` refuse de continuer si une colonne existante risquait de disparaître.

## 5. Appliquer les migrations et vérifier

```sh
uv run python manage.py migrate
uv run python manage.py makemigrations --check
uv run python manage.py collectstatic --noinput
uv run python manage.py runserver
```

`makemigrations --check` doit répondre `No changes detected`. Sinon, il liste
ce qui diffère : en général un champ du fork que vous n’avez pas encore
reporté.

Parcourez ensuite le site et le back-office :

- Les pages publiées s’affichent, avec leurs images et leurs documents.
- Les menus de l’en-tête et du pied de page sont complets.
- Un formulaire s’envoie.
- L’historique d’une page ancienne s’ouvre, et une ancienne version peut être
  prévisualisée.
- La recherche renvoie des résultats.

## 6. Basculer en production

Une fois l’essai concluant, recommencez en production :

1. **Sauvegardez la base de données.**
2. Prévenez les rédacteurs et fermez le back-office pendant la bascule (page
   de maintenance) : toute modification faite entre-temps serait perdue.
3. Arrêtez le fork, déployez le nouveau projet. Si vous utilisez `bern`,
   ajoutez-le aux dépendances (`uv add bern`) et lancez-le avant `migrate` :

   ```sh
   bern apply --yes && python manage.py migrate
   ```

4. Refaites les vérifications de l’étape 5, puis rouvrez le back-office.

:::{warning}
**Le retour en arrière passe par la sauvegarde.** Une fois les pages déplacées
par `bern`, l’ancien code du fork ne peut plus fonctionner avec cette base :
il chercherait des tables qui ont été renommées. Pour revenir en arrière,
restaurez la sauvegarde de l’étape 1 et redéployez le fork.
:::

## Que faire du fork ?

Gardez-le quelques semaines sans le déployer, le temps de vérifier que rien
n’a été oublié, puis archivez-le.

À partir de là, une mise à jour de Sites Conformes se résume à changer un
numéro de version : voir {doc}`nouveau-projet`.
