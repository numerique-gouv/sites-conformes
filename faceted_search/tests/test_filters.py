"""Faceted search filter tests.

Structured like ``publications.tests.test_publication_index_page``: shared filter
cases drive result filtering, sidebar visibility, and combination behaviour.

Blog-specific filters (e.g. category) are not covered here: this project uses
publications, not a standalone blog.
"""

from itertools import combinations
from urllib.parse import urlencode

from django.core.management import call_command
from django.urls import reverse
from wagtail.models import Site

from faceted_search.filters import ENABLED_FILTERS, get_active_filters_from_request_params, get_filter_context
from faceted_search.views import FacetedSearchResultsView
from publications.tests.test_publication_index_page import (
    FILTER_CASES as PUBLICATION_FILTER_CASES,
    PublicationIndexPageFilterTestBase,
)
from sites_conformes.core.search_registry import get_search_results_view


def _query_param_dict(query_string: str) -> dict[str, str]:
    key, _, value = query_string.partition("=")
    return {key: value}


def _replace_filter_url_for_search(case):
    # Publication index cases use ``filter_url`` like ``/publications/?collection=…``;
    # replace it with ``/search/?q=Post&collection=…``.
    return {
        **case,
        "filter_url": lambda self, case=case: self.search_url(**_query_param_dict(case["query_param"](self))),
    }


SEARCH_FILTER_CASES = [_replace_filter_url_for_search(case) for case in PUBLICATION_FILTER_CASES]

FILTER_CONTEXT_KEYS = {
    "filter_by_collection": "collections",
    "filter_by_theme": "themes",
    "filter_by_tag": "tags",
    "filter_by_author": "authors",
    "filter_by_source": "sources",
}

FILTER_FIXTURE_OBJECTS = {
    "filter_by_collection": lambda self: self.collection,
    "filter_by_theme": lambda self: self.theme,
    "filter_by_tag": lambda self: self.tag,
    "filter_by_author": lambda self: self.author,
    "filter_by_source": lambda self: self.organization,
}


def _all_filters_disabled() -> dict[str, bool]:
    return dict.fromkeys(ENABLED_FILTERS, False)


class FacetedSearchFilterTestBase(PublicationIndexPageFilterTestBase):
    filter_cases = SEARCH_FILTER_CASES
    search_query = "Post"

    def setUp(self):
        super().setUp()
        # Indexed for search but title does not match ``search_query`` ("Post").
        self.post_without_search_match = self._create_post(
            "Annual Report",
            collections=[self.collection],
        )
        call_command("update_index")

    def search_url(self, query=None, **params):
        query = self.search_query if query is None else query
        url = reverse("cms_search")
        return f"{url}?{urlencode({'q': query, **params})}"


class FacetedSearchRegistrationTest(FacetedSearchFilterTestBase):
    def test_faceted_search_registers_its_view(self):
        self.assertIs(get_search_results_view().view_class, FacetedSearchResultsView)

    def test_search_uses_faceted_template(self):
        response = self.client.get(self.search_url())
        template_names = [template.name for template in response.templates]
        self.assertIn("faceted_search/search_results.html", template_names)


class FacetedSearchFilterContextTest(FacetedSearchFilterTestBase):
    """``get_filter_context`` builds sidebar lists according to ``enabled_filters``."""

    def _request_and_site(self):
        request = self.client.request().wsgi_request
        site = Site.objects.get(is_default_site=True)
        return request, site

    def test_enabled_filter_flags_populate_context_lists(self):
        for case in self.filter_cases:
            enabled_flags = {**_all_filters_disabled(), case["setting"]: True}
            with self.subTest(case["name"]):
                context = get_filter_context(*self._request_and_site(), enabled_filters=enabled_flags)
                context_key = FILTER_CONTEXT_KEYS[case["setting"]]
                fixture_object = FILTER_FIXTURE_OBJECTS[case["setting"]](self)
                self.assertTrue(context[case["setting"]])
                self.assertIn(fixture_object, list(context[context_key]))

    def test_disabled_filter_flags_omit_context_lists(self):
        context = get_filter_context(*self._request_and_site(), enabled_filters=_all_filters_disabled())
        for case in self.filter_cases:
            with self.subTest(case["name"]):
                context_key = FILTER_CONTEXT_KEYS[case["setting"]]
                self.assertFalse(context[case["setting"]])
                self.assertNotIn(context_key, context)

    def test_show_search_filters_follows_enabled_flags(self):
        enabled_flags = {**_all_filters_disabled(), "filter_by_collection": True}
        context = get_filter_context(*self._request_and_site(), enabled_filters=enabled_flags)
        self.assertTrue(context["show_search_filters"])

        context = get_filter_context(*self._request_and_site(), enabled_filters=_all_filters_disabled())
        self.assertFalse(context["show_search_filters"])


class FacetedSearchFilterQueryTest(FacetedSearchFilterTestBase):
    """Full-text search combined with facet filters (``filter_before_search``)."""

    def test_filters_search_results(self):
        # Each case pairs a matching post with another that also matches ``q=Post``
        # (e.g. "Post Agriculture" vs "Post Environment") but not the active filter.
        # ``post_without_search_match`` may match the facet but not ``q=Post``.
        # The filter must remove the other post from the search results, not just
        # paginate an unfiltered list.
        for case in self.filter_cases:
            with self.subTest(case["name"]):
                response = self.client.get(case["filter_url"](self))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, case["matching_title"](self))
                self.assertNotContains(response, case["other_title"](self))
                self.assertNotContains(response, self.post_without_search_match.title)

    def test_invalid_filter_value_returns_404(self):
        response = self.client.get(self.search_url(collection="nonexistent"))
        self.assertEqual(response.status_code, 404)


class FacetedSearchFilterCombinationTest(FacetedSearchFilterTestBase):
    def test_filters_combine(self):
        # Source interacts with author in fixtures; skip it for pairwise tests.
        filter_cases = [case for case in self.filter_cases if case["name"] != "source"]
        for case_a, case_b in combinations(filter_cases, 2):
            with self.subTest(f"{case_a['name']}+{case_b['name']}"):
                title = f"Post with {case_a['name']} and {case_b['name']}"
                kwargs = {**case_a["post_kwargs"](self), **case_b["post_kwargs"](self)}
                matching = self._create_post(title, **kwargs)
                call_command("update_index")
                params = {
                    **_query_param_dict(case_a["query_param"](self)),
                    **_query_param_dict(case_b["query_param"](self)),
                }
                response = self.client.get(self.search_url(**params))
                # Post with both filters and matching title is returned.
                self.assertContains(response, matching.title)
                for case in (case_a, case_b):
                    # Posts with only one of the two filters are not returned.
                    self.assertNotContains(response, case["matching_title"](self))
                    self.assertNotContains(response, case["other_title"](self))


class FacetedSearchGetActiveFiltersTest(FacetedSearchFilterTestBase):
    def test_get_active_filters_from_request_params(self):
        request = self.client.request().wsgi_request
        request.GET = request.GET.copy()
        request.GET["collection"] = "agriculture"
        request.GET["tag"] = "news"
        site = Site.objects.get(is_default_site=True)
        active = get_active_filters_from_request_params(request, site)
        self.assertEqual(active.collection, self.collection)
        self.assertEqual(active.tag, self.tag)
