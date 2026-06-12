from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from wagtail.models import Page
from wagtail.test.utils import WagtailPageTestCase

from publications.blocks.recent_entries import PUBLICATION_RECENT_ENTRIES_BLOCK
from publications.models import PublicationIndexPage
from sites_conformes.core.models import ContentPage

User = get_user_model()


class PublicationRecentEntriesBlockRegistrationTestCase(SimpleTestCase):
    """The PublicationRecentEntriesBlock is registered with a hook on the
    ContentPage model. Check that it is registered on the top-level body stream block."""

    def test_block_is_registered_on_content_page(self):
        block_names = ContentPage._meta.get_field("body").stream_block.child_blocks
        self.assertIn(PUBLICATION_RECENT_ENTRIES_BLOCK, block_names)


class PublicationRecentEntriesBlockAvailabilityTestCase(WagtailPageTestCase):
    """Test that we can use our custom block within nested blocks in a page (not just top-level)."""

    def setUp(self):
        self.home = Page.objects.get(slug="home")
        self.admin = User.objects.create_superuser("test", "test@test.test", "pass")
        self.index_page = self.home.add_child(
            instance=PublicationIndexPage(title="Publications", slug="publications-availability"),
        )

    def _body_stream_block(self):
        return ContentPage._meta.get_field("body").stream_block

    def _stream_block_at(self, *path):
        block = self._body_stream_block()
        for segment in path:
            block = block.child_blocks[segment]
        return block

    def _assert_block_registered_in_stream(self, *path):
        """Check that the block is registered in the stream block at the given path."""
        stream_block = self._body_stream_block() if not path else self._stream_block_at(*path)
        self.assertIn(PUBLICATION_RECENT_ENTRIES_BLOCK, stream_block.child_blocks)

    def _publication_block_value(self, **overrides):
        return {
            "index_page": self.index_page,
            "entries_count": 3,
            **overrides,
        }

    def _content_page_with_body(self, slug, body):
        return self.home.add_child(
            instance=ContentPage(title="Availability page", slug=slug, owner=self.admin, body=body),
        )

    def _nested_stream_cases(self):
        return (
            (
                "multicolumn column",
                ("multicolumns", "columns", "column", "content"),
                "publication-in-multicolumn-column",
                [
                    (
                        "multicolumns",
                        {
                            "columns": [
                                (
                                    "column",
                                    {
                                        "width": "6",
                                        "content": [
                                            (
                                                PUBLICATION_RECENT_ENTRIES_BLOCK,
                                                self._publication_block_value(title="In a column"),
                                            ),
                                        ],
                                    },
                                ),
                            ],
                        },
                    ),
                ],
                "In a column",
            ),
            (
                "item grid",
                ("item_grid", "items"),
                "publication-in-item-grid",
                [
                    (
                        "item_grid",
                        {
                            "column_width": "4",
                            "items": [
                                (
                                    PUBLICATION_RECENT_ENTRIES_BLOCK,
                                    self._publication_block_value(title="In item grid"),
                                ),
                            ],
                        },
                    ),
                ],
                "In item grid",
            ),
        )

    def test_block_is_registered_in_nested_streams(self):
        for case_label, stream_path, _slug, _body, _title in self._nested_stream_cases():
            with self.subTest(stream=case_label):
                self._assert_block_registered_in_stream(*stream_path)

    def test_can_render_page_with_block_in_nested_streams(self):
        """Programmatically add the block on a page inside the nested path, and check the page is renderable."""
        for case_label, _stream_path, slug, body, title in self._nested_stream_cases():
            with self.subTest(stream=case_label):
                page = self._content_page_with_body(slug, body)
                self.assertPageIsRenderable(page)

                response = self.client.get(page.url)
                block = BeautifulSoup(response.content, "html.parser").select_one(
                    ".cmsfr-block-publication-recent-entries",
                )
                self.assertIsNotNone(block)
                self.assertIn(title, block.get_text())

    # TODO test that the block picker offers the registered block (e2e test)
