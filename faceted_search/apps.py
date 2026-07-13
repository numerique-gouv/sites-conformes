from django.apps import AppConfig


class FacetedSearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "faceted_search"
    label = "faceted_search"

    def ready(self):
        from faceted_search.views import FacetedSearchResultsView
        from sites_conformes.core.search_registry import register_search_view

        register_search_view(FacetedSearchResultsView)
