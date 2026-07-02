from datetime import datetime

from bs4 import BeautifulSoup
from django.utils.translation import gettext

from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme
from sites_conformes.blog.tests.test_blog_index_page import (
    SHARED_FILTER_CASES,
    BlogIndexPageFilterQueryTest,
    BlogIndexPageFilterTestBase,
    BlogIndexPagePostsDisplayTest,
    BlogIndexPageSettingsTest,
)

FILTER_SETTINGS_DEFAULTS = {
    "filter_by_collection": True,
    "filter_by_theme": True,
    "filter_by_tag": True,
    "filter_by_author": False,
    "filter_by_source": False,
}

TAXONOMY_FILTER_CASES = [
    {
        "name": "collection",
        "setting": "filter_by_collection",
        "heading": gettext("Filter by collection"),
        "visible_label": lambda self: self.collection.name,
        "query_param": lambda self: "collection=agriculture",
        "filter_url": lambda self: f"{self.index.url}?collection=agriculture",
        "post_kwargs": lambda self: {"collections": [self.collection]},
        "matching_title": lambda self: self.post_with_collection.title,
        "other_title": lambda self: self.post_with_other_collection.title,
    },
    {
        "name": "theme",
        "setting": "filter_by_theme",
        "heading": gettext("Filter by theme"),
        "visible_label": lambda self: self.theme.name,
        "query_param": lambda self: "theme=climate",
        "filter_url": lambda self: f"{self.index.url}?theme=climate",
        "post_kwargs": lambda self: {"themes": [self.theme]},
        "matching_title": lambda self: self.post_with_theme.title,
        "other_title": lambda self: self.post_with_other_theme.title,
    },
]

FILTER_CASES = TAXONOMY_FILTER_CASES + SHARED_FILTER_CASES


class PublicationIndexPageFilterTestBase(BlogIndexPageFilterTestBase):
    index_page_class = PublicationIndexPage
    index_title = "Publications"
    index_slug = "publications-index"
    filter_cases = FILTER_CASES

    def setup_taxonomy_filter_fixtures(self):
        locale = self.index.locale
        self.collection = Collection.objects.create(
            name="Agriculture",
            slug="agriculture",
            locale=locale,
        )
        self.other_collection = Collection.objects.create(
            name="Environment",
            slug="environment",
            locale=locale,
        )
        self.theme = Theme.objects.create(name="Climate", slug="climate", locale=locale)
        self.other_theme = Theme.objects.create(name="Health", slug="health", locale=locale)

        self.post_with_collection = self._create_post(
            "Post Agriculture",
            collections=[self.collection],
        )
        self.post_with_other_collection = self._create_post(
            "Post Environment",
            collections=[self.other_collection],
        )
        self.post_with_theme = self._create_post("Post Climate", themes=[self.theme])
        self.post_with_other_theme = self._create_post("Post Health", themes=[self.other_theme])

    def _create_post(self, title, collections=None, themes=None, tags=None, authors=None, **_ignored):
        post = PublicationPage(
            title=title,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=self.paris_tz),
            owner=self.admin,
        )
        self.index.add_child(instance=post)
        for collection in collections or []:
            post.collections.add(collection)
        for theme in themes or []:
            post.themes.add(theme)
        for tag in tags or []:
            post.tags.add(tag)
        for author in authors or []:
            post.authors.add(author)
        post.save_revision().publish()
        return post


class PublicationIndexPageSettingsTest(PublicationIndexPageFilterTestBase, BlogIndexPageSettingsTest):
    filter_settings_defaults = FILTER_SETTINGS_DEFAULTS


class PublicationIndexPageFilterQueryTest(
    PublicationIndexPageFilterTestBase,
    BlogIndexPageFilterQueryTest,
):
    pass


class PublicationIndexPagePostsDisplayTest(
    PublicationIndexPageFilterTestBase,
    BlogIndexPagePostsDisplayTest,
):
    def test_posts_display_taxonomies_on_cards(self):
        # Themes are hidden on result cards (publication_index_posts_list.html) because
        # they are too verbose alongside collection tags.
        post = self._create_post(
            "Post with taxonomies",
            collections=[self.collection],
            themes=[self.theme],
        )
        response = self.client.get(self.index.url)  # no filters
        collection_tag = f'<p class="fr-tag">{self.collection.name}</p>'
        theme_tag = f'<p class="fr-tag">{self.theme.name}</p>'
        soup = BeautifulSoup(response.content, "html.parser")
        matching_card = None
        for card in soup.select("div.fr-card"):
            tag_html = "".join(str(tag) for tag in card.select("p.fr-tag"))
            if post.title in card.get_text() and collection_tag in tag_html:
                matching_card = card
                break
        self.assertIsNotNone(
            matching_card,
            "Expected a post card containing the title and the collection tag.",
        )
        self.assertNotIn(theme_tag, "".join(str(tag) for tag in matching_card.select("p.fr-tag")))
