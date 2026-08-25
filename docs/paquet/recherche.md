# Personnalisation de la page de résultats de recherche

Les projets basés sur des forks de Sites conformes ou l’utilisant en mode
paquet peuvent remplacer la page de résultats de recherche par défaut par
leur propre vue et template sans modifier le code du site.

## Mise en place

1. Créer une app hors de  `sites_conformes/`, ou ajouter la vue à une app
existante (voir l’app `faceted_search/` sur le dépôt [Agreste](https://github.com/betagouv/agreste)
pour un exemple complet.)

2. Créez la vue pour la page de résultats. Il doit s’agir d’une sous-classe de
vue Django avec une méthode `as_view()`. Elle remplace complètement la vue
`sites_conformes.core.views.SearchResultsView`, et doit donc implémenter le
comportement de recherche elle-même (queryset, template context, etc.)

3. Définissez le paramètre Django `SEARCH_VIEW` avec le chemin pointé vers
   votre classe de vue :

   ```python
   SEARCH_VIEW = "my_search.views.MySearchResultsView"
   ```

4. Ajoutez l’app à `INSTALLED_APPS`. L’URL `/search/` est déjà câblée dans
   `sites_conformes.core.urls` ; aucune modification d’URL n’est nécessaire.

Une seule vue peut être configurée. Si `SEARCH_VIEW` n’est pas défini, la
vue par défaut `sites_conformes.core.views.SearchResultsView` est utilisée.
