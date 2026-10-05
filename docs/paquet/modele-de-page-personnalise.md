# Modèles de page personnalisés

Les projets utilisant Sites conformes sous forme de paquet peuvent remplacer le
modèle `ContentPage` par leur propre modèle, pour y ajouter des champs, des
panneaux d’administration ou un template spécifique.
C'est la seule solution qui évite de forker le projet.
  
Le mécanisme est celui de `AUTH_USER_MODEL` de Django :

- le paquet fournit une classe abstraite `AbstractContentPage`
- le réglage `SF_CONTENTPAGE_MODEL` désigne le modèle à utiliser.

```{warning}
Le réglage doit être défini **avant la première migration** du projet.
S'il arrivait que des pages soient déjà créées avec le modèle fourni
par sites Conformes, alors celle-ci ne seront pas converties et il
faudra effectuer une migration de données pas forcément évidente.
```

## Mise en place

1. Créez une app django ou utilisez une app existante de
   votre projet.

2. Déclarez votre modèle hérité de `AbstractContentPage`. Le champ `tags`
   et son modèle intermédiaire doivent être déclarés sur votre modèle, car
   celle-ci est requise par Sites Conformes pour bien fonctionner. Le modèle
   intermédiaire du paquet (`TagContentPage`) et sa table ne sont pas créés
   lorsque le modèle est remplacé.

   ```python
   from django.db import models
   from modelcluster.fields import ParentalKey
   from modelcluster.tags import ClusterTaggableManager
   from taggit.models import TaggedItemBase
   from wagtail.admin.panels import FieldPanel

   from sites_conformes.core.models import AbstractContentPage


   class CustomContentPage(AbstractContentPage):
       tags = ClusterTaggableManager(through="TagCustomContentPage", blank=True)
       subtitle = models.CharField(max_length=255, blank=True, default="")

       content_panels = AbstractContentPage.content_panels + [
           FieldPanel("tags"),
           FieldPanel("subtitle"),
       ]


   class TagCustomContentPage(TaggedItemBase):
       content_object = ParentalKey("CustomContentPage", related_name="tagged_items")
   ```

3. Définissez le réglage, au format `app_label.ModelName`, et ajoutez l’app à
   `INSTALLED_APPS` **avant** `sites_conformes.core` afin que ses migrations
   soient appliquées en premier :

   ```python
   INSTALLED_APPS = [
       "my_app",
       # ...
       "sites_conformes.core",
       # ...
   ]

   SF_CONTENTPAGE_MODEL = "my_app.CustomContentPage"
   ```

4. Générez et appliquez les migrations :

   ```sh
   python manage.py makemigrations my_app
   python manage.py migrate
   ```

## Template

Wagtail dérive le nom du template du modèle concret, ici
`my_app/custom_content_page.html`. S’il n’existe pas, le template du paquet
`sites_conformes_core/content_page.html` est utilisé (il en va de même pour
les autres modèles de page). Pour le personnaliser,
créez le template de votre modèle en étendant celui du paquet :

```django
{% extends "sites_conformes_core/content_page.html" %}
```

À noter que vous pouvez, selon vos besoins, fournir un template sur mesure sans
hériter de celui proposé par Sites Conformes. Cependant cela donnera lieux
sur le long terme à davantage de maintenance.

## Les autres modèles de page

Les autres modèles de page du paquet se remplacent de la même manière, chacun
avec son réglage et sa classe abstraite :

| Réglage | Modèle fourni | Classe abstraite |
| --- | --- | --- |
| `SF_CONTENTPAGE_MODEL` | `sites_conformes_core.ContentPage` | `sites_conformes.core.models.AbstractContentPage` |
| `SF_CATALOGINDEXPAGE_MODEL` | `sites_conformes_core.CatalogIndexPage` | `sites_conformes.core.models.AbstractCatalogIndexPage` |
| `SF_BLOGINDEXPAGE_MODEL` | `sites_conformes_blog.BlogIndexPage` | `sites_conformes.blog.models.AbstractBlogIndexPage` |
| `SF_BLOGENTRYPAGE_MODEL` | `sites_conformes_blog.BlogEntryPage` | `sites_conformes.blog.models.AbstractBlogEntryPage` |
| `SF_EVENTSINDEXPAGE_MODEL` | `sites_conformes_events.EventsIndexPage` | `sites_conformes.events.models.AbstractEventsIndexPage` |
| `SF_EVENTENTRYPAGE_MODEL` | `sites_conformes_events.EventEntryPage` | `sites_conformes.events.models.AbstractEventEntryPage` |
| `SF_FORMPAGE_MODEL` | `sites_conformes_forms.FormPage` | `sites_conformes.forms.models.AbstractFormPage` |

Chaque modèle se remplace indépendamment des autres : les pages d’index
acceptent comme sous-pages le modèle désigné par le réglage correspondant, et
les blocs « articles récents » et « événements récents » proposent les pages
d’index remplacées.

Les pages d’index (`AbstractCatalogIndexPage`, `AbstractBlogIndexPage`,
`AbstractEventsIndexPage`) n’ont rien d’autre à déclarer que vos propres champs.

### Articles de blog et événements

Comme pour `tags` sur les pages de contenu, les étiquettes, les catégories et
leurs modèles intermédiaires sont à déclarer sur votre modèle. Les noms des
champs (`tags` et `blog_categories`, ou `event_categories` pour les événements)
sont requis par Sites Conformes ; les panneaux d’administration correspondants
sont déjà fournis par la classe abstraite.

```python
from django.db import models
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.tags import ClusterTaggableManager
from taggit.models import TaggedItemBase

from sites_conformes.blog.models import AbstractBlogEntryPage


class CustomBlogEntryPage(AbstractBlogEntryPage):
    tags = ClusterTaggableManager(through="TagCustomBlogEntryPage", blank=True)
    blog_categories = ParentalManyToManyField(
        "sites_conformes_blog.Category",
        through="CategoryCustomBlogEntryPage",
        blank=True,
        verbose_name="Catégories",
    )


class TagCustomBlogEntryPage(TaggedItemBase):
    content_object = ParentalKey("CustomBlogEntryPage", related_name="tagged_items")


class CategoryCustomBlogEntryPage(models.Model):
    category = models.ForeignKey("sites_conformes_blog.Category", related_name="+", on_delete=models.CASCADE)
    page = ParentalKey("CustomBlogEntryPage", related_name="entry_categories")
```

### Pages de formulaire

Le modèle des champs de formulaire est à déclarer avec votre modèle de page, à
partir de `AbstractFormField`. Le nom `form_fields` est requis.

```python
from django.db import models
from modelcluster.fields import ParentalKey

from sites_conformes.forms.models import AbstractFormField, AbstractFormPage


class CustomFormPage(AbstractFormPage):
    pass


class CustomFormField(AbstractFormField):
    page = ParentalKey("CustomFormPage", on_delete=models.CASCADE, related_name="form_fields")
```

## Accéder aux modèles depuis votre code

N’importez pas directement un modèle fourni par le paquet : une fois remplacé,
il n’est plus utilisable.

```python
from sites_conformes.core import get_model, get_model_string

BlogEntryPage = get_model("SF_BLOGENTRYPAGE_MODEL")  # la classe, une fois les apps chargées
get_model_string("SF_BLOGENTRYPAGE_MODEL")  # "my_app.CustomBlogEntryPage", pour les clés étrangères, subpage_types et migrations
```

Pour les pages de contenu, `get_contentpage_model()` et
`get_contentpage_model_string()` restent disponibles.

## Exemple

L’app `sites_conformes.testapp` du dépôt contient un modèle de référence
pour chaque modèle remplaçable et leur suite de tests, exécutée en CI avec
`just test-swapped`.
Elle peut être utilisée comme source d'inspiration pour voir une mise en oeuvre
complète de cette fonctionnalité.
