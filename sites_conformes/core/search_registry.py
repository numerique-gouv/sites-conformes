"""Registry for fork apps to plug a custom search results view into /search/."""


class SearchRegistry:
    def __init__(self):
        self._view_class = None

    def register(self, view_class):
        self._view_class = view_class

    def clear(self):
        self._view_class = None

    def get_search_results_view(self):
        from sites_conformes.core.views import SearchResultsView

        view_class = self._view_class or SearchResultsView
        return view_class.as_view()


search_registry = SearchRegistry()

register_search_view = search_registry.register
get_search_results_view = search_registry.get_search_results_view
