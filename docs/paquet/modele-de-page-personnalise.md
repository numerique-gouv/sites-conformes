# Modèle de page de contenu personnalisé

Quand on utilise Sites Conformes sous forme de paquet, on peut remplacer le
modèle `ContentPage` par son propre modèle, pour y ajouter des champs, des
panneaux d’administration ou un gabarit spécifique. C’est la seule solution
qui évite de maintenir un fork du projet.

Le mécanisme est le même que pour `AUTH_USER_MODEL` dans Django ou
`WAGTAIL_PAGE_MODEL` dans Wagtail 8 : un réglage désigne le modèle à utiliser,
via la bibliothèque [`swapper`](https://github.com/openwisp/django-swappable-models).
Pas besoin de Wagtail 8 ici, le paquet fournit directement :

- une classe abstraite `AbstractContentPage` ;
- le réglage `SF_CONTENTPAGE_MODEL`, qui désigne le modèle à utiliser.

```{warning}
Définissez le réglage **avant la première migration** du projet. Sur un site
qui a déjà des pages, `migrate` ne les déplace pas : voir
{ref}`changer-de-modele-site-existant`.
```

## Mise en place

1. Créez une application Django ou utilisez une application existante de
   votre projet.

2. Déclarez votre modèle, hérité de `AbstractContentPage`. Le champ `tags` et
   son modèle intermédiaire sont **obligatoires** : les pages d’étiquettes de
   Sites Conformes s’appuient dessus, et la vérification système
   `sites_conformes_core.E001` échoue s’ils manquent. Notez que
   `TagContentPage`, le modèle intermédiaire du paquet, n’est pas créé quand
   le modèle est remplacé. Ci-dessous, `subtitle` est un exemple de champ
   ajouté.

   Les nouveaux champs n’apparaissent dans l’API et la recherche que si vous
   les ajoutez à `api_fields` et `search_fields` :

   ```python
   from django.db import models
   from modelcluster.fields import ParentalKey
   from modelcluster.tags import ClusterTaggableManager
   from taggit.models import TaggedItemBase
   from wagtail.admin.panels import FieldPanel
   from wagtail.api import APIField
   from wagtail.search import index

   from sites_conformes.core.models import AbstractContentPage


   class CustomContentPage(AbstractContentPage):
       tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)
       subtitle = models.CharField(max_length=255, blank=True, default="")

       content_panels = AbstractContentPage.content_panels + [
           FieldPanel("tags"),
           FieldPanel("subtitle"),
       ]

       api_fields = AbstractContentPage.api_fields + [APIField("tags"), APIField("subtitle")]
       search_fields = AbstractContentPage.search_fields + [index.SearchField("subtitle")]


   class TagCustomContentPage(TaggedItemBase):
       content_object = ParentalKey("CustomContentPage", related_name="tagged_items")
   ```

3. Ajoutez l’application à `INSTALLED_APPS` et définissez le réglage, au format
   `app_label.ModelName` :

   ```python
   SF_CONTENTPAGE_MODEL = "my_app.CustomContentPage"
   ```

4. Générez et appliquez les migrations :

   ```sh
   python manage.py makemigrations my_app
   python manage.py migrate
   ```

(changer-de-modele-site-existant)=

## Changer de modèle sur un site existant

Vous avez déjà des pages de contenu, créées avec le modèle du paquet, et vous
voulez passer à votre propre modèle — par exemple parce qu’un champ
supplémentaire est apparu après la mise en ligne, ou parce que vous quittez
un fork ({doc}`depuis-un-fork`).

### Pourquoi `migrate` ne suffit pas

Chaque modèle Django a ses propres tables : vos pages vivent dans celles du
modèle du paquet. En changeant `SF_CONTENTPAGE_MODEL`, Django les cherche
dans les tables de **votre** modèle. `migrate` crée ces tables… vides. Le
site plante alors (`Manager isn't available`) : vos pages sont toujours là,
dans les anciennes tables.

### Ce que fait `bern`

[`bern`](https://github.com/treto-dev/bernard) fait ce déplacement à votre
place. C’est un outil généraliste : il marche avec tout modèle Django
remplaçable par un réglage, comme `AUTH_USER_MODEL`.

Il ne copie pas les pages une à une : il **renomme les tables** de l’ancien
modèle pour qu’elles deviennent celles du vôtre. Concrètement, `bern` :

- renomme les tables de l’ancien modèle vers les noms attendus par le vôtre ;
- ajoute les colonnes des champs que vous avez déclarés en plus ;
- met à jour les types de contenu, dont dépendent les permissions,
  l’historique des pages et l’index de recherche ;
- enregistre la migration initiale de votre application comme déjà appliquée,
  pour que `migrate` reprenne normalement ensuite.

Bilan : aucune ligne copiée ni supprimée. Les pages gardent leur identifiant,
leur adresse, leur historique et leurs étiquettes.

### Étape 1 — Déclarer le modèle

Suivez les étapes 1 à 3 de la mise en place ci-dessus, **sans lancer
`migrate`**.

Le nom de votre modèle est libre, mais deux autres noms sont imposés, car
`bern` et Wagtail s’en servent pour retrouver les données existantes :

- le modèle intermédiaire des étiquettes (`tags`) doit s’appeler
  `TagContentPage`, comme dans le paquet : `bern` reconnaît sa table à ce nom
  et la déplace avec les pages. Avec un autre nom, une table vide serait
  créée à la place et les étiquettes de vos pages ne s’afficheraient plus ;
- son `related_name` doit rester `contentpage_tags` : Wagtail le stocke dans
  l’historique de chaque page, et le garder permet de continuer à restaurer
  les anciennes versions.

```python
class ContentPage(AbstractContentPage):
    tags = ClusterTaggableManager(through="TagContentPage", blank=True)
    subtitle = models.CharField(max_length=255, blank=True, default="")


class TagContentPage(TaggedItemBase):
    content_object = ParentalKey(ContentPage, related_name="contentpage_tags")
```

Générez ensuite la migration de votre application, **sans l’appliquer** :

```sh
python manage.py makemigrations my_app
```

### Étape 2 — Déplacer les pages

:::{important}
**Faites d’abord l’essai sur une copie de la base de production**, voir
{doc}`../donnees/sauvegarde-restauration`.
:::

Depuis le dossier du projet, à côté de `manage.py` :

```sh
uvx bern          # affiche le plan, ne modifie rien
uvx bern apply    # demande le nom de la base, puis applique le plan
python manage.py migrate
```

`uvx bern` ne fait que lire : il trouve le modèle à déplacer dans vos
réglages et affiche le **plan** (tables à renommer, colonnes à ajouter,
migrations à enregistrer). Relisez-le avant de continuer.

`uvx bern apply` applique ce plan, après vous avoir demandé de recopier le
nom de la base de données (protection contre une erreur de cible).

Tout se passe dans **une seule transaction** : en cas d’échec, la base est
inchangée. D’où une limitation : seules PostgreSQL et SQLite savent annuler
un changement de schéma, `bern` refuse les autres.

`bern` s’arrête plutôt que de risquer une perte de données : par exemple, si
un champ existe en base mais pas dans votre modèle, il refuse de continuer
(la colonne disparaîtrait).

### Étape 3 — Vérifier

- Les pages de contenu s’affichent sur le site public.
- Dans le back-office, une page de contenu s’ouvre et s’enregistre.
- Les étiquettes des pages sont toujours là.
- L’historique d’une page ancienne s’ouvre.
- `python manage.py makemigrations --check` répond `No changes detected`.

### En production

En local, `uvx` télécharge `bern` à la volée. Sur un serveur, installez-le
avec le projet :

```sh
uv add bern
```

Sauvegardez la base, puis lancez `bern` au moment du déploiement, entre
l’arrêt de l’ancien code et le démarrage du nouveau :

```sh
bern apply --yes && python manage.py migrate
```

`--yes` supprime la saisie du nom de la base, impossible dans un script de
déploiement.

Relancée, la commande ne fait plus rien une fois le déplacement fait : elle
peut donc rester dans votre script de déploiement sans risque.

:::{warning}
**L’ancien code ne peut plus fonctionner avec cette base** une fois les pages
déplacées : il chercherait des tables qui ont été renommées. Pour revenir en
arrière, restaurez la sauvegarde.
:::

## Mettre à jour Sites Conformes

Les migrations de schéma du paquet ne s’appliquent pas à un modèle remplacé :
après chaque mise à jour, regénérez celles de votre application pour
récupérer les nouveaux champs d’`AbstractContentPage` :

```sh
python manage.py makemigrations my_app
python manage.py migrate
```

## Gabarit

Wagtail déduit le nom du gabarit du modèle concret, ici
`my_app/custom_content_page.html`. S’il n’existe pas, c’est celui du paquet
(`sites_conformes_core/content_page.html`) qui est utilisé. Pour le
personnaliser, créez le gabarit de votre modèle en étendant celui du paquet :

```django
{% extends "sites_conformes_core/content_page.html" %}
```

Vous pouvez aussi écrire un gabarit entièrement sur mesure, sans hériter de
celui du paquet — mais il faudra alors le maintenir vous-même à chaque mise
à jour.

## Accéder au modèle depuis votre code

N’importez pas `ContentPage` directement : une fois le modèle remplacé, il n’est
plus utilisable. Comme pour la `Page` de Wagtail 8, passez par `swapper` :

```python
import swapper

# La classe, une fois les apps chargées (dans une fonction ou une méthode)
ContentPage = swapper.load_model("sites_conformes_core", "ContentPage")

# "my_app.CustomContentPage", utilisable dans les définitions de modèles
# (clés étrangères, subpage_types) et les migrations
swapper.get_model_name("sites_conformes_core", "ContentPage")

# Le modèle choisi, ou False si c’est celui du paquet
swapper.is_swapped("sites_conformes_core", "ContentPage")
```

## Exemple

La démo du dépôt (`demo/`) fait exactement cela avec `home.CustomContentPage`
: voir `demo/home/models.py`, le réglage dans `demo/demo/settings/base.py` et
les tests dans `demo/home/tests.py`, exécutés en CI.
