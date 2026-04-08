"""
Tests for the create_demo_pages management command and the block_to_sample_dict utility.

Two test classes:

- BlockValidationTestCase  – fast, DB-free.  Calls block.to_python() on the
  generated sample value for every block in STREAMFIELD_COMMON_BLOCKS and
  HERO_STREAMFIELD_BLOCKS to catch obvious type mismatches without needing
  a database.

- CreateDemoPagesCommandTestCase – full integration test.  Runs the command
  once (setUpTestData) then verifies that every demo page is renderable.
"""

from django.core.management import call_command
from django.test import SimpleTestCase
from wagtail.models import Site
from wagtail.test.utils import WagtailPageTestCase

from content_manager.blocks.core import HERO_STREAMFIELD_BLOCKS, STREAMFIELD_COMMON_BLOCKS
from content_manager.blocks.utils import block_to_sample_dict
from content_manager.models import ContentPage
from menus.models import MainMenu


class BlockValidationTestCase(SimpleTestCase):
    """
    Fast, DB-free smoke tests.

    For each block in the common and hero stream-block lists we call
    ``block.to_python(block_to_sample_dict(block))`` to verify that the
    generated sample value can at least be deserialised without errors.

    We intentionally do *not* call ``block.clean()`` here because several
    blocks (HeroBackgroundImageBlock, LinkWithoutLabelBlock, …) perform
    cross-field validation that requires real database objects (images,
    pages) or non-None values.  That level of validation is covered by the
    integration test below.
    """

    def _assert_to_python_succeeds(self, name, block):
        value = block_to_sample_dict(block)
        # to_python should not raise for a well-formed sample value
        block.to_python(value)

    def test_all_common_blocks_to_python(self):
        for name, block in STREAMFIELD_COMMON_BLOCKS:
            with self.subTest(block=name):
                self._assert_to_python_succeeds(name, block)

    def test_all_hero_blocks_to_python(self):
        for name, block in HERO_STREAMFIELD_BLOCKS:
            with self.subTest(block=name):
                self._assert_to_python_succeeds(name, block)


class CreateDemoPagesCommandTestCase(WagtailPageTestCase):
    """
    Integration tests for the create_demo_pages management command.

    The command is run once for the whole class (setUpTestData) then each
    test asserts that the relevant page is renderable through the full
    template stack.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        call_command("create_demo_pages", verbosity=0)

    # ------------------------------------------------------------------
    # common_blocks page
    # ------------------------------------------------------------------

    def test_common_blocks_page_is_renderable(self):
        page = ContentPage.objects.get(slug="common_blocks")
        self.assertPageIsRenderable(page)

    def test_each_block_type_in_common_blocks_is_present(self):
        page = ContentPage.objects.get(slug="common_blocks")
        block_types = {entry.block_type for entry in page.body}

        # blog_recent_entries and events_recent_entries require existing
        # blog/events index pages, so they are intentionally omitted from
        # the demo page.
        expected = {
            "paragraph",
            "image",
            "imageandtext",
            "table",
            "alert",
            "text_cta",
            "video",
            "transcription",
            "badges_list",
            "tags_list",
            "buttons_list",
            "link",
            "accordions",
            "callout",
            "highlight",
            "quote",
            "stepper",
            "card",
            "tile",
            "tabs",
            "markdown",
            "iframe",
            "html",
            "anchor",
            "separator",
            "multicolumns",
            "item_grid",
            "fullwidthbackground",
            "fullwidthbackgroundwithsidemenu",
            "subpageslist",
            "layout_richtext",
            "image_text_grid_section",
            "image_text_cta_section",
            "cta_section",
            "spotlight_section",
            "accordion_section",
        }
        self.assertEqual(block_types, expected)

    # ------------------------------------------------------------------
    # hero_blocks sub-pages
    # ------------------------------------------------------------------

    def test_hero_text_image_page_is_renderable(self):
        page = ContentPage.objects.get(slug="hero-text-image")
        self.assertPageIsRenderable(page)

    def test_hero_text_wide_image_page_is_renderable(self):
        page = ContentPage.objects.get(slug="hero-text-wide-image")
        self.assertPageIsRenderable(page)

    def test_hero_text_background_image_page_is_renderable(self):
        page = ContentPage.objects.get(slug="hero-text-background-image")
        self.assertPageIsRenderable(page)

    def test_hero_old_page_is_renderable(self):
        page = ContentPage.objects.get(slug="hero-old")
        self.assertPageIsRenderable(page)

    # ------------------------------------------------------------------
    # main menu
    # ------------------------------------------------------------------

    def test_main_menu_is_created(self):
        site = Site.objects.get(is_default_site=True)
        self.assertTrue(MainMenu.objects.filter(site=site).exists())

    def test_main_menu_has_four_items(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        self.assertEqual(len(menu.items), 4)

    def test_main_menu_first_item_links_to_home_page(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        first = menu.items[0]
        self.assertEqual(first.block_type, "link")
        self.assertEqual(first.value["page"], site.root_page)

    def test_main_menu_second_item_is_publications_megamenu(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        second = menu.items[1]
        self.assertEqual(second.block_type, "megamenu")
        self.assertEqual(second.value["label"], "Publications")

    def test_main_menu_publications_megamenu_has_four_columns(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        columns = menu.items[1].value["columns"]
        self.assertEqual(len(columns), 4)

    def test_main_menu_publications_megamenu_columns_have_eight_links_each(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        columns = menu.items[1].value["columns"]
        for column in columns:
            with self.subTest(column=column.value["label"]):
                self.assertEqual(len(column.value["links"]), 8)

    def test_main_menu_third_item_links_to_menu_page(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        third = menu.items[2]
        self.assertEqual(third.block_type, "link")
        self.assertEqual(third.value["page"].slug, "menu_page")

    def test_main_menu_fourth_item_links_to_blog_index(self):
        site = Site.objects.get(is_default_site=True)
        menu = MainMenu.objects.get(site=site)
        fourth = menu.items[3]
        self.assertEqual(fourth.block_type, "link")
        self.assertEqual(fourth.value["page"].slug, "actualités")
