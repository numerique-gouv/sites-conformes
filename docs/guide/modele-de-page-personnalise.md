# Personnaliser le modèle de page de contenu

Le modèle `ContentPage` est interchangeable, sur le même principe que
`AUTH_USER_MODEL` de Django ou `WAGTAILIMAGES_IMAGE_MODEL` de Wagtail : vous
pouvez fournir votre propre modèle de page de contenu (champs supplémentaires,
panneaux d'édition, méthodes métier…) tout en conservant les fonctionnalités
du package (pages catalogue, étiquettes, commandes de création de pages,
import/export…).

:::{warning}
Le modèle doit être choisi **avant la création des premières pages**,
idéalement au démarrage du projet. Changer de modèle sur un site existant
nécessite une migration de données (voir [plus bas](#migrer-un-site-existant)).
:::

## 1. Déclarer le modèle

Dans une application de votre projet, créez un modèle héritant de
`AbstractContentPage` :

```python
# myapp/models.py
from modelcluster.fields import ParentalKey
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase

from sites_conformes.core.abstract import AbstractContentPage


class CustomContentPage(AbstractContentPage):
    # Réutilise le gabarit fourni par le package. Sans cette ligne, Wagtail
    # cherchera "myapp/custom_content_page.html".
    template = "sites_conformes_core/content_page.html"

    # Le gestionnaire d'étiquettes doit être déclaré sur le modèle concret,
    # car son modèle intermédiaire pointe vers un modèle concret.
    tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)

    # Vos champs supplémentaires…


class TagCustomContentPage(TaggedItemBase):
    content_object = ParentalKey("CustomContentPage", related_name="customcontentpage_tags")
```

Deux éléments sont volontairement laissés à la charge du modèle concret :

- **`tags`** : le modèle intermédiaire taggit (`TaggedItemBase`) repose sur
  une `ParentalKey` vers un modèle concret ; il doit donc être redéclaré,
  comme pour les modèles d'image personnalisés de Wagtail.
- **`template`** : Wagtail dérive le gabarit du `app_label` du modèle ;
  précisez `template` pour réutiliser le gabarit fourni.

## 2. Pointer le réglage

```python
# settings.py
SF_CONTENTPAGE_MODEL = "myapp.CustomContentPage"
```

Une vérification système (`sites_conformes.E001` / `sites_conformes.E002`)
valide au démarrage que le modèle existe et hérite bien de
`AbstractContentPage`.

## 3. Générer les migrations

```bash
python manage.py makemigrations myapp
python manage.py migrate
```

## Référencer le modèle dans votre code

Ne référencez jamais `ContentPage` directement dans du code générique ;
utilisez les accesseurs :

```python
from sites_conformes.core.model_utils import get_contentpage_model, get_contentpage_model_string

# La classe de modèle
ContentPage = get_contentpage_model()

# La chaîne "app_label.ModelName", pour les ForeignKey, subpage_types, etc.
subpage_types = [get_contentpage_model_string()]
```

## Migrer un site existant

Si des pages `ContentPage` existent déjà, le changement de réglage ne les
convertit pas : les pages Wagtail sont liées à leur type via
`content_type` et une table par modèle (héritage multi-table). Il faut une
migration de données qui, pour chaque page existante :

1. crée une ligne dans la table du nouveau modèle (`ptr` vers la même ligne
   `wagtailcore_page`) ;
2. met à jour `content_type` de la page vers le nouveau modèle.

C'est la même démarche que celle décrite par Wagtail pour
[migrer vers un modèle d'image personnalisé après coup](https://docs.wagtail.org/en/stable/advanced_topics/images/custom_image_model.html#migrating-from-the-builtin-image-model).
Testez impérativement sur une copie de la base.

## Limites connues

- Les attributs résolus à la définition des classes (par exemple
  `CatalogIndexPage.subpage_types`) lisent le réglage au démarrage :
  `override_settings` ne les affecte pas dans les tests, et le réglage doit
  être en place avant le lancement de l'application.
- La table du modèle `ContentPage` par défaut reste créée même si le modèle
  est remplacé (comme pour `wagtailimages.Image`). Elle reste simplement vide.
