# Cas pratique - annuaire de psychologues sur une carte

Ce guide répond à une question récurrente : comment ajouter une entité métier
(par exemple un annuaire de psychologues), l'afficher sur une carte
interactive, et l'exposer via une API ?

Le parcours :

1. Installer `sites-conformes` dans un projet Django existant.
2. Modéliser l'entité `Psychologue` comme un **snippet** Wagtail.
3. Créer un **bloc StreamField** réutilisable qui affiche la liste sur une carte.
4. Exposer le tout via l'API REST de Wagtail (`/api/v2/`).

## 0. Prérequis

`sites-conformes` doit être installé et configuré dans votre projet Django.
Voir [Installation](installation.md) si ce n'est pas fait.

Le guide utilise [`uv`](https://docs.astral.sh/uv/) pour gérer l'environnement
Python et exécuter les commandes Django (`uv run python ...`). Si vous
préférez un autre gestionnaire, retirez le préfixe `uv run` : les commandes
restent identiques.

L'exemple suppose une app Django locale nommée `annuaire` :

```bash
uv run python manage.py startapp annuaire
```

Ajoutez `"annuaire"` à `INSTALLED_APPS`, juste après les apps `sites_conformes.*`.

:::{note}
Une implémentation complète et exécutable de ce guide se trouve dans
[`demo/annuaire/`](https://github.com/fabienheureux/paquet-facile/tree/main/demo/annuaire).
Pour la lancer :

- clonez le dépôt et placez-vous dans `demo/`
- lancez `just setup` (installe les dépendances, applique les migrations et
  insère des psychologues + une page d'annuaire publiée à `/annuaire/`)
- lancez `just runserver` puis ouvrez <http://localhost:8000/annuaire/>
:::

## 1. Le snippet `Psychologue`

Un [snippet Wagtail](https://docs.wagtail.org/en/stable/topics/snippets/index.html)
est un modèle Django éditable depuis le back office sans qu'il s'agisse d'une
page. Parfait pour des données réutilisables sur plusieurs pages : un annuaire
de psys, une liste de lieux, des contacts.

On stocke les coordonnées en
[`DecimalField`](https://docs.djangoproject.com/en/stable/ref/models/fields/#decimalfield)
plutôt qu'en
[`PointField`](https://docs.djangoproject.com/en/stable/ref/contrib/gis/model-api/#pointfield)
(PostGIS), pour rester sur une stack Postgres ou SQLite standard. Pour les
requêtes spatiales avancées (recherche par rayon, etc.), passez à
[`django.contrib.gis`](https://docs.djangoproject.com/en/stable/ref/contrib/gis/).

```python
# annuaire/models.py
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet


@register_snippet
class Psychologue(models.Model):
    nom = models.CharField(max_length=120)
    ville = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        help_text="Latitude WGS84 (ex: 48.856614 pour Paris)",
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6,
        help_text="Longitude WGS84 (ex: 2.352222 pour Paris)",
    )

    panels = [
        FieldPanel("nom"),
        FieldPanel("ville"),
        FieldPanel("email"),
        FieldPanel("telephone"),
        FieldPanel("latitude"),
        FieldPanel("longitude"),
    ]

    class Meta:
        ordering = ("nom",)
        verbose_name = "Psychologue"
        verbose_name_plural = "Psychologues"

    def __str__(self):
        return f"{self.nom} ({self.ville})"
```

Migrations :

```bash
uv run python manage.py makemigrations annuaire
uv run python manage.py migrate
```

Le snippet apparaît dans l'admin Wagtail sous **Snippets → Psychologues**.

## 2. Un bloc StreamField qui affiche la carte

Pour intégrer la carte dans une page, on crée un [bloc
Wagtail](https://docs.wagtail.org/en/stable/topics/streamfield.html). Comme
l'éditeur ne doit pas saisir manuellement les psys - ils viennent de la base -
on utilise
[`StaticBlock`](https://docs.wagtail.org/en/stable/reference/streamfield/blocks.html#wagtail.blocks.StaticBlock)
: un bloc sans champs éditables qui rend simplement un template à partir du
contexte fourni par
[`get_context()`](https://docs.wagtail.org/en/stable/topics/streamfield.html#custom-context).

```python
# annuaire/blocks.py
from wagtail import blocks

from .models import Psychologue


class ListePsychologuesBlock(blocks.StaticBlock):
    """Affiche la liste des psychologues sur une carte interactive."""

    class Meta:
        icon = "group"
        label = "Liste des psychologues (carte)"
        template = "annuaire/blocks/liste_psychologues.html"
        admin_text = "Affiche tous les psychologues sur une carte Carte Facile."

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        qs = Psychologue.objects.all()
        context["psychologues"] = qs
        # Sérialisation JSON-safe : les DecimalField deviennent des float
        # pour le passage côté JavaScript.
        context["psychologues_geojson"] = [
            {
                "nom": psy.nom,
                "ville": psy.ville,
                "lat": float(psy.latitude),
                "lng": float(psy.longitude),
            }
            for psy in qs
        ]
        return context
```

## 3. Le template : carte interactive avec Carte Facile

[Carte Facile](https://fab-geocommuns.github.io/carte-facile-site/) est une
bibliothèque de styles cartographiques fournie par la Fabrique des Géocommuns
(IGN). Elle s'appuie sur [`maplibre-gl`](https://maplibre.org/) pour le rendu.

Pour un POC, le plus simple est de charger les deux via CDN (`unpkg.com`) avec
un *import map* - pas de bundler nécessaire :

```html
{# annuaire/templates/annuaire/blocks/liste_psychologues.html #}
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css">
<link rel="stylesheet" href="https://unpkg.com/carte-facile@0.9.0/dist/carte-facile.css">

<section class="fr-container fr-py-6w" aria-labelledby="annuaire-titre">
  <h2 id="annuaire-titre" class="fr-h3">Annuaire des psychologues</h2>

  <div class="fr-grid-row fr-grid-row--gutters">
    <div class="fr-col-12 fr-col-md-7">
      <div id="annuaire-carte"
           style="height: 480px; width: 100%;"
           role="application"
           aria-label="Carte interactive de l'annuaire"></div>
    </div>
    <div class="fr-col-12 fr-col-md-5">
      <ul class="fr-list" style="max-height: 480px; overflow-y: auto;">
        {% for psy in psychologues %}
          <li>
            <strong>{{ psy.nom }}</strong> &mdash; {{ psy.ville }}
            {% if psy.email %}<br><a href="mailto:{{ psy.email }}">{{ psy.email }}</a>{% endif %}
          </li>
        {% empty %}
          <li>Aucun psychologue dans l'annuaire pour le moment.</li>
        {% endfor %}
      </ul>
    </div>
  </div>

  {# `json_script` sérialise correctement avec l'échappement requis. #}
  {{ psychologues_geojson|json_script:"annuaire-data" }}

  <script type="importmap">
    {
      "imports": {
        "maplibre-gl": "https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js",
        "carte-facile": "https://unpkg.com/carte-facile@0.9.0/dist/carte-facile.esm.js"
      }
    }
  </script>

  <script type="module">
    import maplibregl from "maplibre-gl";
    import { mapStyles } from "carte-facile";

    const data = JSON.parse(document.getElementById("annuaire-data").textContent);

    const map = new maplibregl.Map({
      container: "annuaire-carte",
      style: mapStyles.simple,
      center: [2.5, 47.0],   // centre France
      zoom: 5,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }));

    map.on("load", () => {
      if (data.length === 0) return;
      const bounds = new maplibregl.LngLatBounds();
      for (const psy of data) {
        const popup = new maplibregl.Popup({ offset: 18 }).setHTML(
          `<strong>${psy.nom}</strong><br>${psy.ville}`
        );
        new maplibregl.Marker()
          .setLngLat([psy.lng, psy.lat])
          .setPopup(popup)
          .addTo(map);
        bounds.extend([psy.lng, psy.lat]);
      }
      map.fitBounds(bounds, { padding: 40, maxZoom: 10 });
    });
  </script>
</section>
```

## 4. Brancher le bloc sur une page

Le plus simple est de définir une `AnnuairePage` (une
[`Page` Wagtail](https://docs.wagtail.org/en/stable/topics/pages.html)) qui
expose un
[`StreamField`](https://docs.wagtail.org/en/stable/topics/streamfield.html)
contenant **uniquement** notre bloc :

```python
# annuaire/models.py (suite)
from wagtail.fields import StreamField
from wagtail.models import Page


def _annuaire_stream_blocks():
    # Lazy-import pour éviter un cycle blocks ↔ models.
    from .blocks import ListePsychologuesBlock
    return [("liste_psychologues", ListePsychologuesBlock())]


class AnnuairePage(Page):
    body = StreamField(_annuaire_stream_blocks, blank=True, use_json_field=True)

    content_panels = Page.content_panels + [FieldPanel("body")]
```

Pour ajouter votre bloc **à toutes** les pages `sites-conformes`, héritez de
`CommonStreamBlock` à la place - voir
`sites_conformes.core.blocks.CommonStreamBlock` et le pattern utilisé par
[quefairedemesobjets/webapp/qfdmd/blocks.py](https://github.com/fab-geocommuns/quefairedemesobjets).

:::{warning}
Hériter de `CommonStreamBlock` couple votre site aux blocs `sites-conformes` :
**à chaque montée de version où `sites-conformes` modifie ses blocs communs,
Django détectera un changement de `StreamField` et exigera une migration côté
projet hôte** (`uv run python manage.py makemigrations` puis `migrate`).
C'est un compromis connu de l'approche par héritage. La page d'exemple ci-dessus
(`AnnuairePage` avec un `StreamField` qui ne contient que notre bloc) n'a pas
ce problème : elle reste stable tant que vous ne touchez pas à
`ListePsychologuesBlock`.
:::

Migration, puis dans l'admin Wagtail vous pouvez créer une *Annuaire page* et
sa carte se rend automatiquement à partir des `Psychologue` en base.

## 5. Exposer les psychologues via l'API Wagtail

Wagtail fournit nativement une
[API REST v2](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/configuration.html)
en `/api/v2/`.

### 5.1 Endpoint snippets

Wagtail expose les **pages** et les **images/documents** par défaut, mais
**pas les snippets**. On écrit un
[viewset personnalisé](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/configuration.html#adding-more-api-endpoints)
:

```python
# annuaire/api.py
from rest_framework import serializers
from wagtail.api.v2.views import BaseAPIViewSet

from .models import Psychologue


class PsychologueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Psychologue
        fields = ["id", "nom", "ville", "email", "telephone", "latitude", "longitude"]


class PsychologuesAPIViewSet(BaseAPIViewSet):
    model = Psychologue
    base_serializer_class = PsychologueSerializer
    body_fields = BaseAPIViewSet.body_fields + [
        "nom", "ville", "email", "telephone", "latitude", "longitude",
    ]
    listing_default_fields = BaseAPIViewSet.listing_default_fields + ["nom", "ville"]
```

### 5.2 Enregistrement sur le routeur

`sites-conformes` instancie déjà le routeur Wagtail dans
`sites_conformes.config.api.api_router`. On ajoute notre endpoint depuis
`AppConfig.ready()` :

```python
# annuaire/apps.py
from django.apps import AppConfig


class AnnuaireConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "annuaire"
    verbose_name = "Annuaire"

    def ready(self):
        from sites_conformes.config.api import api_router
        from .api import PsychologuesAPIViewSet
        api_router.register_endpoint("psychologues", PsychologuesAPIViewSet)
```

Cette approche évite de modifier les `urls.py` du projet : le routeur reste
celui de `sites-conformes`, on l'enrichit depuis notre app.

### 5.3 Exemples d'appels

```bash
# Liste de tous les psychologues, format JSON
curl http://localhost:8000/api/v2/psychologues/

# Un seul, par id
curl http://localhost:8000/api/v2/psychologues/42/

# Filtrer par ville (filtres Wagtail standards)
curl "http://localhost:8000/api/v2/psychologues/?ville=Lyon"

# Pagination - limit/offset
curl "http://localhost:8000/api/v2/psychologues/?limit=20&offset=40"
```

Les pages contenant le bloc *Liste des psychologues* sont également
disponibles via [`/api/v2/pages/`](https://docs.wagtail.org/en/stable/advanced_topics/api/v2/usage.html),
et le `StreamField` `body` apparaît sérialisé en JSON.
