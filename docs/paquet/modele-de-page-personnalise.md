# Modèle de page de contenu personnalisé

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
   celle-ci est requise par Sites Conformes pour bien fonctionner

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
`sites_conformes_core/content_page.html` est utilisé. Pour le personnaliser,
créez le template de votre modèle en étendant celui du paquet :

```django
{% extends "sites_conformes_core/content_page.html" %}
```

À noter que vous pouvez, selon vos besoins, fournir un template sur mesure sans
hériter de celui proposé par Sites Conformes. Cependant cela donnera lieux
sur le long terme à davantage de maintenance.

## Accéder au modèle depuis votre code

N’importez pas `ContentPage` directement : une fois le modèle remplacé, il n’est
plus utilisable.

```python
from sites_conformes.core import get_contentpage_model, get_contentpage_model_string

ContentPage = get_contentpage_model()  # la classe, une fois les apps chargées
ContentPage = get_contentpage_model_string()  # "my_app.CustomContentPage", pour les clés étrangères, subpage_types et migrations
```

## Exemple

L’app `sites_conformes.testapp` du dépôt contient un modèle de référence
complet et sa suite de tests, exécutée en CI avec `just test-swapped`.
Elle peut être utilisée comme source d'inspiration pour voir une mise en oeuvre
complète de cette fonctionnalité.
