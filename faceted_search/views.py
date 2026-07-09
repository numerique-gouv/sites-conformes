from faceted_search.filters import filter_queryset, get_filter_context
from sites_conformes.core.views import SearchResultsView as BaseSearchResultsView


class FacetedSearchResultsView(BaseSearchResultsView):
    """Search with sidebar filters (collection, theme, tag, etc.)."""

    def filter_search_queryset(self, queryset, site):
        return filter_queryset(self.request, queryset, site)

    def get_search_filter_context(self, site):
        return get_filter_context(self.request, site)
