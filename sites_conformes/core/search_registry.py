"""Registry for fork apps to plug a custom search results view into ``/search/``.

How to add a custom search app
==============================

Fork projects can replace the default search page with their own view and
template without editing ``sites_conformes``.

1. Create a Django app outside ``sites_conformes/`` (see ``faceted_search/``
   in https://github.com/betagouv/agreste for a full example).

2. Subclass :class:`~sites_conformes.core.views.SearchResultsView` and override
   the extension points as needed:

   - ``filter_search_queryset(queryset, site)`` — narrow the queryset before
     ``.search()`` is called
   - ``get_search_filter_context(site)`` — extra template context (e.g. a
     filter sidebar)
   - ``template_name`` — your app's search results template

3. Register the view when the app starts::

       # my_search/apps.py
       def ready(self):
           from my_search.views import MySearchResultsView
           from sites_conformes.core.search_registry import register_search_view

           register_search_view(MySearchResultsView)

4. Add the app to ``INSTALLED_APPS``. The ``/search/`` URL is already wired in
   ``sites_conformes.core.urls``; no URL changes are required.

Only one view can be registered. If several apps call ``register_search_view``,
the last registration wins (determined by ``INSTALLED_APPS`` order).

Templates can extend ``sites_conformes_core/search_results.html`` and override
the ``search_sidebar``, ``search_results_column_class``, ``search_results``, and
``search_no_results`` blocks.
"""

from sites_conformes.core.views import SearchResultsView


class SearchRegistry:
    def __init__(self):
        self._view_class = None

    def register(self, view_class):
        self._view_class = view_class

    def clear(self):
        self._view_class = None

    def get_search_results_view(self):
        view_class = self._view_class or SearchResultsView
        return view_class.as_view()


search_registry = SearchRegistry()

register_search_view = search_registry.register
get_search_results_view = search_registry.get_search_results_view
