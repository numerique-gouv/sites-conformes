from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils.translation import gettext
from wagtail.blocks import BoundBlock, CharBlock, ListBlock

from sites_conformes.core.abstract import SitesFacilesBasePage
from sites_conformes.core.blocks.related_entries import BlogRecentEntriesBlock
from sites_conformes.core.models import ContentPage
from sites_conformes.core.search_description import (
    SEARCH_DESCRIPTION_MAX_CHARS,
    _html_to_text,
    get_search_description,
    get_streamblock_raw_text,
)


def _body(data):
    return ContentPage._meta.get_field("body").to_python(data)


def _hero(data):
    return ContentPage._meta.get_field("hero").to_python(data)


class SearchDescriptionTestCase(SimpleTestCase):
    def test_paragraph_text_is_extracted(self):
        body = _body(
            [
                {
                    "type": "paragraph",
                    "value": "<p>A short description of this page.</p>",
                }
            ]
        )

        result = get_search_description(body)

        self.assertEqual(result, "A short description of this page.")

    def test_multicolumns_column_width_and_content_labels_are_omitted(self):
        body = _body(
            [
                {
                    "type": "multicolumns",
                    "value": {
                        "title": "",
                        "heading_tag": "h2",
                        "top_margin": 5,
                        "bottom_margin": 5,
                        "columns": [
                            {
                                "type": "column",
                                "value": {
                                    "width": "8",
                                    "content": [
                                        {
                                            "type": "text",
                                            "value": "<p>Inner column prose about agriculture.</p>",
                                        }
                                    ],
                                },
                            }
                        ],
                    },
                }
            ]
        )

        result = get_search_description(body)

        self.assertEqual(result, "Inner column prose about agriculture.")
        self.assertNotIn("width", result.lower())
        self.assertNotIn("content", result.lower())
        self.assertNotIn("8", result)

    def test_short_text_is_not_truncated(self):
        body = _body(
            [
                {
                    "type": "paragraph",
                    "value": "<p>A short description of this page.</p>",
                }
            ]
        )

        result = get_search_description(body, max_chars=SEARCH_DESCRIPTION_MAX_CHARS)

        self.assertEqual(result, "A short description of this page.")
        self.assertFalse(result.endswith("[...]"))

    def test_long_text_is_truncated_at_word_boundary(self):
        body = _body([{"type": "paragraph", "value": "<p>one two three four</p>"}])

        self.assertEqual(get_search_description(body, max_chars=10), "one two [...]")

    def test_listblock_children_are_extracted_without_error(self):
        list_block = ListBlock(CharBlock())
        bound = BoundBlock(list_block, list_block.to_python(["Hello", "world"]))

        self.assertEqual(get_streamblock_raw_text(bound), "Hello. world")

    def test_broken_block_is_skipped(self):
        class FakeBlock:
            name = "paragraph"

        class BrokenBlock:
            block = FakeBlock()

            @property
            def value(self):
                raise RuntimeError("cannot read block")

        kept = BoundBlock(CharBlock(), "Kept text")
        also_kept = BoundBlock(CharBlock(), "Also kept")

        with self.assertLogs("sites_conformes.core.search_description", level="ERROR"):
            result = get_search_description([kept, BrokenBlock(), also_kept])

        self.assertEqual(result, "Kept text. Also kept")

    def test_combined_streamfields_keep_order(self):
        first = _body([{"type": "paragraph", "value": "<p>Hero heading</p>"}])
        second = _body([{"type": "paragraph", "value": "<p>Body paragraph.</p>"}])

        result = get_search_description(first, second)

        self.assertEqual(result, "Hero heading. Body paragraph.")

    @patch(
        "sites_conformes.core.blocks.medias.Image.objects.filter",
        return_value=MagicMock(first=MagicMock(return_value=None)),
    )
    def test_hero_text_is_extracted(self, _mock_filter):
        hero = _hero(
            [
                {
                    "type": "hero_text_image",
                    "value": {
                        "text_content": {
                            "hero_title": "Hero heading",
                            "hero_subtitle": "<p>Hero description of the organisation.</p>",
                            "position": "left",
                        },
                        "buttons": [
                            {
                                "text": "Click this button",
                                "link_type": "external_url",
                                "external_url": "https://example.com",
                            }
                        ],
                    },
                }
            ]
        )

        result = get_search_description(hero)

        self.assertEqual(result, "Hero heading. Hero description of the organisation. Click this button")
        self.assertNotIn("https://example.com", result)

    @patch(
        "sites_conformes.core.blocks.medias.Image.objects.filter",
        return_value=MagicMock(first=MagicMock(return_value=None)),
    )
    def test_hero_text_comes_before_body(self, _mock_filter):
        hero = _hero(
            [
                {
                    "type": "hero_text_image",
                    "value": {
                        "text_content": {
                            "hero_title": "Hero heading",
                            "hero_subtitle": "<p>Hero description.</p>",
                            "position": "left",
                        },
                        "buttons": [],
                    },
                }
            ]
        )
        body = _body(
            [
                {
                    "type": "paragraph",
                    "value": "<p>Body paragraph.</p>",
                }
            ]
        )

        result = get_search_description(hero, body)

        self.assertEqual(result, "Hero heading. Hero description. Body paragraph.")

    def test_blocks_are_joined_with_punctuation(self):
        body = _body(
            [
                {"type": "paragraph", "value": "<p>First block.</p>"},
                {"type": "paragraph", "value": "<p>Introduction:</p>"},
                {"type": "paragraph", "value": "<p>Details below;</p>"},
                {"type": "paragraph", "value": "<p>More text</p>"},
            ]
        )

        self.assertEqual(
            get_search_description(body),
            "First block. Introduction: Details below; More text",
        )

    def test_button_labels_are_included(self):
        body = _body(
            [
                {"type": "paragraph", "value": "<p>Intro text.</p>"},
                {
                    "type": "buttons_list",
                    "value": {
                        "buttons": [
                            {
                                "type": "button",
                                "value": {
                                    "link_type": "external_url",
                                    "text": "Click this button",
                                    "external_url": "https://example.com",
                                },
                            }
                        ],
                    },
                },
            ]
        )

        result = get_search_description(body)

        self.assertEqual(result, "Intro text. Click this button")
        self.assertNotIn("https://example.com", result)
        self.assertNotIn(gettext("Opens a new window"), result)

    def test_html_to_text_strips_hidden_and_script_content(self):
        html = (
            "<p>Visible copy.</p>"
            '<span class="fr-sr-only">Opens a new window</span>'
            '<span class="visually-hidden">Skip this</span>'
            "<div hidden>Hidden block</div>"
            '<span aria-hidden="true">Tooltip</span>'
            "<script>alert(1)</script>"
            "<style>p { color: red; }</style>"
        )

        self.assertEqual(_html_to_text(html), "Visible copy.")

    def test_html_to_text_joins_headings_paragraphs_and_standalone_links(self):
        html = '<h2>Section title</h2><p>A paragraph.</p><a class="fr-btn" href="/go">Click</a>'

        self.assertEqual(_html_to_text(html), "Section title. A paragraph. Click")

    def test_html_to_text_keeps_inline_links_inside_paragraphs(self):
        html = '<p>See the <a href="/docs">documentation</a> here.</p>'

        self.assertEqual(_html_to_text(html), "See the documentation here.")

    def test_richtext_heading_and_paragraph_are_joined(self):
        body = _body(
            [
                {
                    "type": "paragraph",
                    "value": "<h3>Section title</h3><p>Details here.</p>",
                }
            ]
        )

        self.assertEqual(get_search_description(body), "Section title. Details here.")

    def test_table_caption_headings_and_cells_are_extracted(self):
        body = _body(
            [
                {
                    "type": "table",
                    "value": {
                        "columns": [
                            {"type": "text", "heading": "Name"},
                            {"type": "text", "heading": "Comment"},
                        ],
                        "rows": [
                            {
                                "values": [
                                    '<p data-block-key="ab12c">Line 1</p>',
                                    '<p data-block-key="def34g">Example text with <b>formating</b>.</p>',
                                ]
                            },
                        ],
                        "caption": "Example table",
                    },
                }
            ]
        )

        result = get_search_description(body)

        self.assertEqual(result, "Example table. Name. Comment. Line 1. Example text with formating.")

    def test_recent_entries_listing_titles_are_omitted(self):
        inner = BlogRecentEntriesBlock()
        inner.set_name("blog_recent_entries")
        bound = BoundBlock(
            inner,
            inner.to_python(
                {
                    "title": "Latest news",
                    "heading_tag": "h2",
                    "see_all_button_text": "See all posts",
                }
            ),
        )

        with patch.object(bound, "render") as mock_render:
            result = get_streamblock_raw_text(bound)

        mock_render.assert_not_called()
        self.assertEqual(result, "Latest news. See all posts")

    def test_fill_search_description_on_unsaved_page(self):
        page = type("DummyPage", (), {})()
        page.search_description = ""
        page.hero = None
        page.body = _body([{"type": "paragraph", "value": "<p>Hello from the body.</p>"}])

        SitesFacilesBasePage._fill_search_description(page)

        self.assertEqual(page.search_description, "Hello from the body.")

    def test_fill_search_description_does_not_overwrite_existing(self):
        page = type("DummyPage", (), {})()
        page.search_description = "Custom description"
        page.hero = None
        page.body = _body([{"type": "paragraph", "value": "<p>Hello from the body.</p>"}])

        SitesFacilesBasePage._fill_search_description(page)

        self.assertEqual(page.search_description, "Custom description")
