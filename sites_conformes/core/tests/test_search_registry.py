from django.test import SimpleTestCase, override_settings
from django.views.generic import View

from sites_conformes.core.search_registry import _resolve_search_view, get_search_results_view
from sites_conformes.core.views import SearchResultsView


class DummySearchView(View):
    marker = "dummy"


class NotAView:
    pass


class SearchRegistryTest(SimpleTestCase):
    def setUp(self):
        _resolve_search_view.cache_clear()

    def tearDown(self):
        _resolve_search_view.cache_clear()

    @override_settings(SEARCH_VIEW=None)
    def test_default_view_is_core_search_results_view(self):
        self.assertIs(get_search_results_view().view_class, SearchResultsView)

    @override_settings(SEARCH_VIEW="")
    def test_empty_string_view_falls_back_to_default(self):
        # An empty string is treated as "not configured", like many optional Django settings.
        self.assertIs(get_search_results_view().view_class, SearchResultsView)

    @override_settings(SEARCH_VIEW="sites_conformes.core.tests.test_search_registry.DummySearchView")
    def test_setting_replaces_default_view(self):
        self.assertIs(get_search_results_view().view_class, DummySearchView)

    @override_settings(SEARCH_VIEW="nonexistent.module.View")
    def test_invalid_view_path_is_logged_and_raises(self):
        with self.assertLogs("sites_conformes.core.search_registry", level="ERROR") as captured_logs:
            with self.assertRaises(Exception):
                get_search_results_view()
        self.assertIn("nonexistent.module.View", captured_logs.output[0])

    @override_settings(SEARCH_VIEW="sites_conformes.core.tests.test_search_registry.NotAView")
    def test_non_view_class_raises(self):
        with self.assertRaises(TypeError):
            get_search_results_view()
