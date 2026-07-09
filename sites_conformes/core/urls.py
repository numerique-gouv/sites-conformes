from django.apps import apps as django_apps
from django.urls import include, path
from django.utils.translation import gettext_lazy as _
from wagtail import urls as wagtail_urls

from sites_conformes.core.views import SearchResultsView, SiteMapView, TagsListView, TagView


def get_search_results_view():
    if django_apps.is_installed("search"):
        from search.views import SearchResultsView as FilteredSearchResultsView

        return FilteredSearchResultsView.as_view()
    return SearchResultsView.as_view()


urlpatterns = [
    path(_("search/"), get_search_results_view(), name="cms_search"),
    path(_("sitemap/"), SiteMapView.as_view(), name="readable_sitemap"),
    path("tags/<str:tag>/", TagView.as_view(), name="global_tag"),
    path("tags/", TagsListView.as_view(), name="global_tags_list"),
    path("", include(wagtail_urls)),
]
