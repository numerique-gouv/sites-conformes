from django.test import SimpleTestCase

from sites_conformes.core.search_registry import (
    get_search_results_view,
    register_search_view,
    search_registry,
)
from sites_conformes.core.views import SearchResultsView


class DummySearchView(SearchResultsView):
    marker = "dummy"


class SearchRegistryTest(SimpleTestCase):
    def setUp(self):
        self._saved_view = search_registry._view_class

    def tearDown(self):
        search_registry._view_class = self._saved_view

    def test_default_view_is_core_search_results_view(self):
        search_registry.clear()
        self.assertIs(get_search_results_view().view_class, SearchResultsView)

    def test_register_replaces_default_view(self):
        register_search_view(DummySearchView)
        self.assertIs(get_search_results_view().view_class, DummySearchView)
