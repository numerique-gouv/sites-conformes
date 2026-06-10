from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from wagtail.models import Page
from wagtail.rich_text import RichText
from wagtail.test.utils import WagtailPageTestCase

from publications.blocks.recent_entries import PUBLICATION_RECENT_ENTRIES_BLOCK
from publications.models import Collection, PublicationIndexPage, PublicationPage, Theme
from sites_conformes.core.models import ContentPage

User = get_user_model()


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
