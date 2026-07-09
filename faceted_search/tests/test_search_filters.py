from django.core.management import call_command
from django.urls import reverse
from django.utils.translation import gettext

from publications.tests.test_publication_index_page import PublicationIndexPageFilterTestBase


class SearchFilterTestBase(PublicationIndexPageFilterTestBase):
    def setUp(self):
        super().setUp()
        call_command("update_index")

    def search_url(self, query="Post", **params):
        url = reverse("cms_search")
        query_string = f"q={query}"
        for key, value in params.items():
            query_string += f"&{key}={value}"
        return f"{url}?{query_string}"


class SearchCollectionFilterTest(SearchFilterTestBase):
    def test_search_filter_by_collection(self):
        response = self.client.get(self.search_url(collection="agriculture"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post_with_collection.title)
        self.assertNotContains(response, self.post_with_other_collection.title)

    def test_search_filter_sidebar_shows_collections(self):
        response = self.client.get(self.search_url())
        self.assertContains(response, gettext("Filter by collection"))
        self.assertContains(response, self.collection.name)


class SearchThemeFilterTest(SearchFilterTestBase):
    def test_search_filter_by_theme(self):
        response = self.client.get(self.search_url(theme="climate"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post_with_theme.title)
        self.assertNotContains(response, self.post_with_other_theme.title)


class SearchTagFilterTest(SearchFilterTestBase):
    def test_search_filter_by_tag(self):
        response = self.client.get(self.search_url(tag="news"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post_with_tag.title)
        self.assertNotContains(response, self.post_with_other_tag.title)

    def test_search_filter_sidebar_shows_tags(self):
        response = self.client.get(self.search_url())
        self.assertContains(response, gettext("Filter by tag"))
        self.assertContains(response, self.tag.name)
