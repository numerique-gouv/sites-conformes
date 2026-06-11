import zoneinfo
from datetime import datetime
from itertools import combinations

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from publications.blocks.recent_entries import PUBLICATION_RECENT_ENTRIES_BLOCK
from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme
from sites_conformes.blog.models import Organization, Person
from sites_conformes.core.models import ContentPage, Tag

User = get_user_model()

FILTER_SPECS = {
    "collection": {
        "block_field": "collection_filter",
        "value": lambda test_case: test_case.collection,
        "post_kwargs": lambda test_case: {"collections": [test_case.collection]},
        "matching_post": lambda test_case: test_case.post_with_collection,
        "other_post": lambda test_case: test_case.post_with_other_collection,
    },
    "theme": {
        "block_field": "theme_filter",
        "value": lambda test_case: test_case.theme,
        "post_kwargs": lambda test_case: {"themes": [test_case.theme]},
        "matching_post": lambda test_case: test_case.post_with_theme,
        "other_post": lambda test_case: test_case.post_with_other_theme,
    },
    "tag": {
        "block_field": "tag_filter",
        "value": lambda test_case: test_case.tag,
        "post_kwargs": lambda test_case: {"tags": [test_case.tag]},
        "matching_post": lambda test_case: test_case.post_with_tag,
        "other_post": lambda test_case: test_case.post_with_other_tag,
    },
    "author": {
        "block_field": "author_filter",
        "value": lambda test_case: test_case.author,
        "post_kwargs": lambda test_case: {"authors": [test_case.author]},
        "matching_post": lambda test_case: test_case.post_with_author,
        "other_post": lambda test_case: test_case.post_with_other_author,
    },
    "source": {
        "block_field": "source_filter",
        "value": lambda test_case: test_case.organization,
        "post_kwargs": lambda test_case: {"authors": [test_case.author]},
        "matching_post": lambda test_case: test_case.post_with_author,
        "other_post": lambda test_case: test_case.post_with_other_author,
    },
}


class PublicationRecentEntriesBlockRegistrationTestCase(SimpleTestCase):
    """The PublicationRecentEntriesBlock is registered with a hook on the
    ContentPage model. Check that it is registered."""

    def test_block_is_registered_on_content_page(self):
        block_names = ContentPage._meta.get_field("body").stream_block.child_blocks
        self.assertIn(PUBLICATION_RECENT_ENTRIES_BLOCK, block_names)


class PublicationRecentEntriesBlockTestCase(WagtailPageTestCase):
    def setUp(self):
        home_page = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")

        lorem_body = [("paragraph", RichText("<p>Lorem ipsum.</p>"))]

        self.index_page = home_page.add_child(
            instance=PublicationIndexPage(title="Publications", body=lorem_body, slug="publications"),
        )
        self.collection = Collection.objects.create(name="Agriculture", slug="agriculture")
        self.theme = Theme.objects.create(name="Climate", slug="climate")

        self.post = self.index_page.add_child(
            instance=PublicationPage(
                title="Report",
                slug="report",
                body=lorem_body,
                collections=[self.collection],
                themes=[self.theme],
            ),
        )

        body = [
            (
                PUBLICATION_RECENT_ENTRIES_BLOCK,
                {
                    "title": "Latest",
                    "heading_tag": "h2",
                    "index_page": self.index_page,
                    "entries_count": 4,
                    "collection_filter": self.collection,
                    "show_filters": True,
                },
            ),
        ]
        self.content_page = home_page.add_child(
            instance=ContentPage(title="Sample page", slug="publication-recent-block", owner=self.admin, body=body),
        )

    def test_publication_recent_entries_is_renderable(self):
        self.assertPageIsRenderable(self.content_page)

    def test_publication_recent_entries_shows_collection_tags(self):
        response = self.client.get(self.content_page.url)
        self.assertContains(response, self.collection.name)
        self.assertContains(response, self.post.title)


class PublicationRecentEntriesBlockFilterTestCase(WagtailPageTestCase):
    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.paris_tz = zoneinfo.ZoneInfo("Europe/Paris")

        self.index_page = self.home.add_child(
            instance=PublicationIndexPage(
                title="Publications",
                slug="publications-recent-filters",
                owner=self.admin,
            ),
        )
        self.index_page.save_revision().publish()

        locale = self.index_page.locale
        self.collection = Collection.objects.create(name="Agriculture", slug="agriculture", locale=locale)
        self.other_collection = Collection.objects.create(name="Environment", slug="environment", locale=locale)
        self.theme = Theme.objects.create(name="Climate", slug="climate", locale=locale)
        self.other_theme = Theme.objects.create(name="Health", slug="health", locale=locale)
        self.tag = Tag.objects.create(name="News", slug="news")
        self.other_tag = Tag.objects.create(name="Report", slug="report")
        self.organization = Organization.objects.create(name="INRAE", slug="inrae")
        self.other_organization = Organization.objects.create(name="ANSES", slug="anses")
        self.author = Person.objects.create(name="Jane Doe", role="Writer", organization=self.organization)
        self.other_author = Person.objects.create(
            name="John Smith",
            role="Editor",
            organization=self.other_organization,
        )

        self.post_with_collection = self._create_post("Post Agriculture", collections=[self.collection])
        self.post_with_other_collection = self._create_post("Post Environment", collections=[self.other_collection])
        self.post_with_theme = self._create_post("Post Climate", themes=[self.theme])
        self.post_with_other_theme = self._create_post("Post Health", themes=[self.other_theme])
        self.post_with_tag = self._create_post("Post News", tags=[self.tag])
        self.post_with_other_tag = self._create_post("Post Report", tags=[self.other_tag])
        self.post_with_author = self._create_post("Post Jane", authors=[self.author])
        self.post_with_other_author = self._create_post("Post John", authors=[self.other_author])

    def _create_post(self, title, collections=None, themes=None, tags=None, authors=None):
        post = PublicationPage(
            title=title,
            date=datetime(2024, 1, 1, 12, 0, 0, tzinfo=self.paris_tz),
            owner=self.admin,
        )
        self.index_page.add_child(instance=post)
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

    def _render_block_page(self, slug, **block_fields):
        """Put the block on a ContentPage, render it, and return the HTTP response."""
        content_page = self.home.add_child(
            instance=ContentPage(
                title="Recent entries block",
                slug=slug,
                owner=self.admin,
                body=[
                    (
                        PUBLICATION_RECENT_ENTRIES_BLOCK,
                        {
                            "index_page": self.index_page,
                            "entries_count": 20,
                            **block_fields,
                        },
                    ),
                ],
            ),
        )
        response = self.client.get(content_page.url)
        self.assertEqual(response.status_code, 200)
        return response

    def _card_titles_in_block(self, response):
        """Post titles rendered inside the recent-entries block cards."""
        block = BeautifulSoup(response.content, "html.parser").select_one(
            ".cmsfr-block-publication-recent-entries",
        )
        self.assertIsNotNone(block)
        return [link.get_text(strip=True) for link in block.select(".fr-card__title a")]

    def test_single_filters(self):
        for name, spec in FILTER_SPECS.items():
            with self.subTest(filter=name):
                response = self._render_block_page(
                    slug=f"recent-filter-{name}",
                    **{spec["block_field"]: spec["value"](self)},
                )
                titles = self._card_titles_in_block(response)
                self.assertIn(spec["matching_post"](self).title, titles)
                self.assertNotIn(spec["other_post"](self).title, titles)

    def test_two_filter_combinations(self):
        # Source is excluded from pairwise combinations because it filters via
        # authors__organization and overlaps with author filtering.
        combination_names = ("collection", "theme", "tag", "author")

        for first, second in combinations(combination_names, 2):
            with self.subTest(filters=(first, second)):
                first_spec = FILTER_SPECS[first]
                second_spec = FILTER_SPECS[second]
                matching_post = self._create_post(
                    f"Post {first} and {second}",
                    **first_spec["post_kwargs"](self),
                    **second_spec["post_kwargs"](self),
                )
                response = self._render_block_page(
                    slug=f"recent-filter-{first}-{second}",
                    **{
                        first_spec["block_field"]: first_spec["value"](self),
                        second_spec["block_field"]: second_spec["value"](self),
                    },
                )
                self.assertEqual(self._card_titles_in_block(response), [matching_post.title])
