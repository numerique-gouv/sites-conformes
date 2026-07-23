"""Registry for fork apps to plug a custom search results view into ``/search/``.

How to add a custom search view
===============================

Fork projects can replace the default search page with their own view and
template without editing ``sites_conformes``.

1. Create a Django app outside ``sites_conformes/``, or add the view to an
   existing app (see ``faceted_search/`` in https://github.com/betagouv/agreste
   for a full example).

2. Implement a search results view. It should be a Django ``View`` subclass
   with an ``as_view()`` class method. It completely replaces
   :class:`~sites_conformes.core.views.SearchResultsView`, so it must implement
   the full search behaviour itself (queryset, template context, etc.).

3. Set the ``SEARCH_VIEW`` Django setting to the dotted path of your view
   class::

       SEARCH_VIEW = "my_search.views.MySearchResultsView"

4. Add the app to ``INSTALLED_APPS``. The ``/search/`` URL is already wired in
   ``sites_conformes.core.urls``; no URL changes are required.

Only one view can be configured. If ``SEARCH_VIEW`` is not set, the default
``sites_conformes.core.views.SearchResultsView`` is used.
"""

import logging
from functools import lru_cache

from django.conf import settings
from django.utils.module_loading import import_string

from sites_conformes.core.views import SearchResultsView

logger = logging.getLogger(__name__)


# Cache by view_path so we do not re-import the module on every search request.
# Tests still work because the cache key is the path string; changing SEARCH_VIEW
# via override_settings produces a different key and resolves a different class.
@lru_cache(maxsize=None)
def _resolve_search_view(view_path):
    """Return the configured search view class, falling back to the default."""
    if not view_path:
        return SearchResultsView

    try:
        view_class = import_string(view_path)
    except Exception:
        logger.error("Invalid SEARCH_VIEW setting: %r", view_path)
        raise

    if not isinstance(view_class, type) or not callable(getattr(view_class, "as_view", None)):
        raise TypeError(f"SEARCH_VIEW {view_path!r} must be a Django view class with as_view()")

    return view_class


def get_search_results_view():
    """Return the configured search view as a view callable."""
    view_path = getattr(settings, "SEARCH_VIEW", None)
    view_class = _resolve_search_view(view_path)
    return view_class.as_view()
